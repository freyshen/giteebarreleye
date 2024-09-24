"""
Coral command
"""
# pylint: disable=unused-import
import sys
import os
import traceback
from fire import Fire
from pycoral import constant
from pycoral import cmd_general
from pycoral import ssh_host
from pycoral import lustre_version
from pybuild import coral_build
from pybuild import build_common
from pybuild import config_check_command


def build(coral_command,
          cache=constant.CORAL_BUILD_CACHE,
          lustre=None,
          e2fsprogs=None,
          collectd=None,
          disable_creaf=False,
          enable_zfs=False,
          enable_devel=False,
          only_plugin=None,
          disable_plugin=None,
          china=False):
    """
    Build the Coral ISO.
    :param debug: Whether to dump debug logs into files, default: False.
    :param cache: The dir that caches build RPMs. Default:
        /var/log/coral/build_cache.
    :param lustre: The dir of Lustre RPMs (usually generated by lbuild).
        Default: /var/log/coral/build_cache/$type/iso_cache/lustre_release.
    :param e2fsprogs: The dir of E2fsprogs RPMs.
        Default: /var/log/coral/build_cache/$type/iso_cache/e2fsprogs.
    :param collectd: The Collectd source codes.
        Default: https://github.com/LiXi-storage/collectd/releases/$latest.
        A local source dir or .tar.bz2 generated by "make dist" of Collectd
        can be specified if modification to Collectd is needed.
    :param disable_creaf: whether disable Reaf C codes. Default: False.
    :param enable_zfs: Whether enable ZFS support. Default: False.
    :param enable_devel: Whether enable development support. Default: False.
    :param disable_plugin: Disable one or more plugins. To disable multiple
        plugins, please provide a list seperated by comma
        (e.g. clownf,barrele). Default: None.
    :param only_plugin: Only build one or more plugins. To build multiple
        plugins, please provide a list seperated by comma
        (e.g. clownf,barrele). Default: None.
    :param china: Whether use local mirrors. If specified, will
        replace mirrors for possible speedup. Default: False.
    """
    # pylint: disable=unused-argument,protected-access,too-many-locals
    if not isinstance(coral_command._cc_log_to_file, bool):
        print("ERROR: invalid debug option [%s], should be a bool type" %
              (coral_command._cc_log_to_file), file=sys.stderr)
        sys.exit(1)

    source_dir = os.getcwd()
    identity = build_common.get_build_path()
    logdir_is_default = True
    log, workspace = cmd_general.init_env_noconfig(source_dir,
                                                   coral_command._cc_log_to_file,
                                                   logdir_is_default,
                                                   identity=identity)
    local_host = ssh_host.get_local_host(ssh=False)
    cache = cmd_general.check_argument_str(log, "cache", cache)
    if lustre is not None:
        lustre = cmd_general.check_argument_fpath(log, local_host, lustre)
    if e2fsprogs is not None:
        e2fsprogs = cmd_general.check_argument_fpath(log, local_host, e2fsprogs)
    if collectd is not None:
        collectd = cmd_general.check_argument_fpath(log, local_host, collectd)

    cmd_general.check_argument_bool(log, "enable_zfs", enable_zfs)
    cmd_general.check_argument_bool(log, "enable_devel", enable_devel)
    if disable_plugin is not None:
        disable_plugin = cmd_general.check_argument_list_str(log, "disable_plugin",
                                                             disable_plugin)
    if only_plugin is not None:
        only_plugin = cmd_general.check_argument_list_str(log, "only_plugin",
                                                          only_plugin)

    cmd_general.check_argument_bool(log, "china", china)
    # Coram command entrance should have configured china mirrors, so do not
    # pass this argument down. The param is left here only for generating
    # manual.
    rc = coral_build.build(log, source_dir, workspace, cache=cache,
                           lustre_dir=lustre,
                           e2fsprogs_dir=e2fsprogs,
                           collectd=collectd,
                           enable_zfs=enable_zfs,
                           enable_devel=enable_devel,
                           disable_creaf=disable_creaf,
                           disable_plugin=disable_plugin,
                           only_plugin=only_plugin,
                           china=False)
    cmd_general.cmd_exit(log, rc)


build_common.coral_command_register("build", build)


def plugins(coral_command):
    """
    List the plugins of Coral.
    """
    # pylint: disable=unused-argument
    plugin_str = ""
    for plugin in build_common.CORAL_PLUGIN_DICT.values():
        if plugin_str == "":
            plugin_str = plugin.cpt_plugin_name
        else:
            plugin_str += "," + plugin.cpt_plugin_name
    sys.stdout.write(plugin_str + '\n')


build_common.coral_command_register("plugins", plugins)


def detect_lustre(coral_command, fpath):
    """
    Detect the Lustre version from RPM names.
    :param fpath: The file path that saves RPM names with or with out .rpm suffix.
    """
    # pylint: disable=protected-access,too-many-locals
    source_dir = os.getcwd()
    identity = build_common.get_build_path()
    logdir_is_default = True
    log, _ = cmd_general.init_env_noconfig(source_dir,
                                           coral_command._cc_log_to_file,
                                           logdir_is_default,
                                           identity=identity)

    try:
        with open(fpath, "r", encoding='utf-8') as fd:
            lines = fd.readlines()
    except:
        log.cl_error("failed to read file [%s]: %s",
                     fpath, traceback.format_exc())
        cmd_general.cmd_exit(log, -1)

    rpm_fnames = []
    for line in lines:
        line = line.strip()
        fields = line.split()
        for rpm_fname in fields:
            if not rpm_fname.endswith(".rpm"):
                rpm_fname += ".rpm"
            rpm_fnames.append(rpm_fname)
            log.cl_info("RPM: %s", rpm_fname)

    local_host = ssh_host.get_local_host(ssh=False)
    version_db = lustre_version.load_lustre_version_database(log, local_host,
                                                             constant.LUSTRE_VERSION_DEFINITION_DIR)
    if version_db is None:
        log.cl_error("failed to load version database [%s]",
                     constant.LUSTRE_VERSION_DEFINITION_DIR)
        cmd_general.cmd_exit(log, 0)

    version, _ = version_db.lvd_match_version_from_rpms(log,
                                                        rpm_fnames,
                                                        skip_kernel=True,
                                                        skip_test=True)
    if version is None:
        version, _ = version_db.lvd_match_version_from_rpms(log,
                                                            rpm_fnames,
                                                            client=True)
        if version is None:
            log.cl_error("failed to match Lustre version according to RPM names")
            cmd_general.cmd_exit(log, -1)
        log.cl_stdout("Lustre client: %s", version.lv_version_name)
        cmd_general.cmd_exit(log, 0)
    log.cl_stdout("Lustre server: %s", version)
    cmd_general.cmd_exit(log, 0)


build_common.coral_command_register("detect_lustre", detect_lustre)


def main():
    """
    main routine
    """
    Fire(build_common.CoralCommand)
