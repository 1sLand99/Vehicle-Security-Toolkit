#!/usr/bin/python3

import shutil
import argparse
from pathlib import Path
from utils import shell_cmd_ret_code


def analysis_cli(src_path: Path):
    print(f'[+] {src_path} - cli')

    scanner = Path(__file__).parent.joinpath('tools/dependency-check/bin/dependency-check.sh')
    report = src_path.joinpath('dependency-check-report.html')
    cmd = f'{scanner} -s {src_path} -o {report}'
    return shell_cmd_ret_code(cmd)


def analysis_gradle(src_path: Path):
    print(f'[+] {src_path} - gradle')

    build1 = str(src_path.joinpath('build.gradle'))

    # 备份
    shutil.copy(build1, build1+'.bak')

    # 修改
    sed1 = 'sed -i \"/dependencies {/a\classpath \'org.owasp:dependency-check-gradle:6.5.3\'\" '+build1
    sed2 = 'sed -i \"/repositories {/a\mavenCentral()\" '+build1
    sed3 = 'sed -i \"/allprojects {/a\\apply plugin: \'org.owasp.dependencycheck\'\\ndependencyCheck {scanConfigurations += \'releaseRuntimeClasspath\'}\" '+build1

    shell_cmd_ret_code(f'{sed1} && {sed2} && {sed3}')

    # 运行
    env = {
        'ANDROID_HOME': Path('~').expanduser().joinpath('Android/Sdk'),
        'ANDROID_SDK_ROOT': Path('~').expanduser().joinpath('Android/Sdk'),
        'DOTNET_CLI_HOME': '/tmp/dotnethome',
        'LC_ALL': 'C.UTF-8'
    }
    cmd = f'cd {src_path} && chmod +x gradlew && ./gradlew dependencyCheckAnalyze'
    output, ret_code = shell_cmd_ret_code(cmd, env=env)
    if 'Could not determine java version' in output:
        cmd = f'source {Path("~").expanduser().joinpath(".sdkman/bin/sdkman-init.sh")} && sdk use java 8.0.312-tem && {cmd}'
        output, ret_code = shell_cmd_ret_code(cmd, env=env, exe='/bin/zsh')
    if ret_code == 0:
        # 生成依赖关系图
        cmd = f'cd {src_path} && chmod +x gradlew && ./gradlew -q projects 2>&1 | grep Project | cut -d "\'" -f 2'
        output, _ = shell_cmd_ret_code(cmd, env=env)
        # 遍历根模块和所有子模块
        for subproject in output.splitlines()+['']:
            cmd = f'cd {src_path} && chmod +x gradlew && ./gradlew {subproject}:dependencies'
            output, _ = shell_cmd_ret_code(cmd, env=env)

            subdir = subproject.replace(':', '/')[1:] if subproject else '.'
            #if Path(subdir)
            with open(src_path.joinpath(f'{subdir}/build/reports/dependency-check-graph.txt'), 'w+') as f:
                f.write(output)
    else:
        print(f'[-] {src_path} gradlew 运行失败')
        output, ret_code = analysis_cli(src_path)

    # 恢复
    shutil.move(build1+'.bak', build1)

    # 清理
    shutil.rmtree(src_path.joinpath('.gradle'), ignore_errors=True)
    #for i in list(Path(build1).parent.rglob('dependency-check-report.html')):
    #    shutil.rmtree(i.parent.parent, ignore_errors=True)
    return output, ret_code


def analysis(src_path: Path, mode: str):
    if mode == 'cli':
        output, ret_code = analysis_cli(src_path)
    elif mode == 'gradle':
        output, ret_code = analysis_gradle(src_path)
    else:
        return False

    if ret_code != 0:
        with open(src_path.joinpath(f'dependency-check-report.html.error'), 'w+') as f:
            f.write(output)

    return ret_code


def argument():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", help="A config file containing source code paths to run analysis", type=str, required=True)
    return parser.parse_args()


if __name__ == '__main__':
    print('****************** src-depcheck.py *******************')

    failed = []
    success_num = 0
    config_file = argument().config
    if config_file:
        src_dirs = open(config_file, 'r').read().splitlines()

        for src in src_dirs:
            src_path = Path(src)
            if src_path.joinpath('gradlew').exists():
                ret = analysis(src_path, 'gradle')
            else:
                ret = analysis(src_path, 'cli')

            if ret == 0:
                success_num += 1
            else:
                failed.append(src)
    else:
        print('[!] 参数错误: python3 src-depcheck.py --help')

    print(f'扫描完成: {success_num}, 扫描失败: {len(failed)}')
    print('\n'.join(failed))