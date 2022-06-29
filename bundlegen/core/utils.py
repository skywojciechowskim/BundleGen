# If not stated otherwise in this file or this component's license file the
# following copyright and licenses apply:
#
# Copyright 2020 Consult Red
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import subprocess
import shlex
import uuid
import tarfile
import time
import os
import shutil

from loguru import logger


class Utils:

    # ==========================================================================
    @staticmethod
    def run_process(command):
        """Runs the process with the specified command

        Will stream the stdout of the process to the console

        Args:
            command (string): Command with args to run

        Returns:
            int: Return code from the process
        """
        # Run the process
        process = subprocess.Popen(shlex.split(
            command), shell=False, stdout=subprocess.PIPE)

        # Monitor the stdout and print to the screen
        for line in iter(process.stdout.readline, b''):
            logger.debug(line.strip().decode())

        # Process has finished, clean up and get the return code
        process.stdout.close()
        return_code = process.wait()
        return return_code

    # ==========================================================================
    @staticmethod
    def run_process_and_return_output(command):
        """Runs the process with the specified command
        Will return the stdout of the process
        Args:
            command (string): Command with args to run
        Returns:
            int: Return code from the process
            string: stdout from the process
        """
        # Run the process
        process = subprocess.Popen(shlex.split(
            command), shell=False, stdout=subprocess.PIPE)

        out, err = process.communicate()

        # Process has finished, clean up and get the return code
        process.stdout.close()
        return_code = process.wait()
        return return_code, out.decode()

    # ==========================================================================
    @staticmethod
    def get_random_string(length=32):
        """Creates a string of random characters

        Args:
            length (int, optional): Length of the string to generate. Defaults to 32.

        Returns:
            string: Random string
        """
        string = uuid.uuid4().hex.lower()

        if length >= len(string):
            return string

        return string[:length]

    # ==========================================================================
    @staticmethod
    def create_control_file(platform, app_metadata):

        package_name = app_metadata.get("id", "test_package")
        version = app_metadata.get("version", "1.0.0")
        architecture = ""
        if platform.get('arch'):
            architecture = str(platform['arch'].get('arch')) + str(platform['arch'].get('variant'))
        description = app_metadata.get("description", "some package")
        priority = app_metadata.get("priority", "optional")
        depends = "" # we never depend on anything

        with open("control", "w") as file:
            file.write(f"Package: {package_name}\n")
            file.write(f"Version: {version}\n")
            file.write(f"Architecture: {architecture}\n")
            file.write(f"Description: {description}\n")
            file.write(f"Priority: {priority}\n")
            file.write(f"Depends: {depends}\n")

    # ==========================================================================
    @staticmethod
    def add_tarinfo(tar, tarinfo, name, name_in_archive, uid, gid, mode_mask):
        if uid:
            tarinfo.uid = uid
            tarinfo.uname = str(uid)
        if gid:
            tarinfo.gid = gid
            tarinfo.gname = str(gid)
        if mode_mask:
            tarinfo.mode &= int(mode_mask, 8)

        if tarinfo.isreg():
            with open(name, "rb") as f:
                tar.addfile(tarinfo, f)
        elif tarinfo.isdir():
            tar.addfile(tarinfo)
            for f in os.listdir(name):
                name_child = os.path.join(name, f)
                name_in_archive_child = os.path.join(name_in_archive, f)
                tarinfo_child = tar.gettarinfo(name_child, name_in_archive_child)
                Utils.add_tarinfo(tar, tarinfo_child, name_child, name_in_archive_child,
                    uid, gid, mode_mask)
        else:
            tar.addfile(tarinfo)

    # ==========================================================================
    @staticmethod
    def create_tgz(source, dest, uid = None, gid = None, mode_mask = None):
        """Create a .tar.gz file of the source directory. Contents of source directory
        is at the root of the tar.gz file.

        Args:
            source (string): Path to directory to compress
            dest (string): Where to save the tarball
            uid (int): if set, force this uid as owner on all files/dirs inside tarball
            gid (int): if set, force this gid as group on all files/dirs inside tarball
            mode_mask (string): if set, apply this mask on all files/dirs inside tarball
                                for example '770' will remove all rights for 'other' users

        Returns:
            bool: True for success
        """

        if not dest.endswith(".tar.gz"):
            output_filename = f'{dest}.tar.gz'
        else:
            output_filename = dest

        logger.info(f"Creating tgz of {source} as {output_filename}")
        source = os.path.abspath(source)

        # Make sure the bundle is at the root of the tarball
        source = source + '/'

        if not os.path.exists(source):
            logger.error("Cannot create tar - source directory does not exist")
            return False

        if os.path.exists(output_filename):
            os.remove(output_filename)

        with tarfile.open(f'{output_filename}', "w:gz") as tar:
            if (uid or gid or mode_mask):
                tarinfo = tar.gettarinfo(name=source, arcname=os.path.basename(source))
                Utils.add_tarinfo(tar, tarinfo, source, os.path.basename(source), uid, gid, mode_mask)
            else:
                tar.add(source, arcname=os.path.basename(source))

        return True

    # ==========================================================================
    @staticmethod
    def create_ipk(source, dest):
        """Create a .ipk file of the source directory. Contents of source directory
        is at the root of the tar.gz file.

        Args:
            source (string): Path to directory to compress
            dest (string): Where to save the tarball

        Returns:
            bool: True for success
        """

        # define const names
        DATA_NAME = "data.tar.gz"
        CONTROL_NAME = "control.tar.gz"
        DEBIAN_BIN_NAME = "debian-binary"

        if not dest.endswith(".ipk"):
            output_filename = f'{dest}.ipk'
        else:
            output_filename = dest


        # first create tarball with complete filesystem
        Utils.create_tgz(source, DATA_NAME)

        # create "control" directory
        with tarfile.open(CONTROL_NAME, "w:gz") as tar:
            # control file should be created before by calling create_control_file
            tar.add("control")

        # create debian-binary file
        with open(DEBIAN_BIN_NAME, "w") as file:
            file.write("2.0")

        # create ipk bundle
        with tarfile.open(f'{output_filename}', "w:gz") as tar:
            tar.add(DATA_NAME)
            tar.add(CONTROL_NAME)
            tar.add(DEBIAN_BIN_NAME)

        # remove temp files
        os.remove("control")
        os.remove(DATA_NAME)
        os.remove(CONTROL_NAME)
        os.remove(DEBIAN_BIN_NAME)

        return True


    # ==========================================================
    @staticmethod
    def create_sky_widget(source, dest):
        if not dest.endswith(".wgt"):
            output_filename = f'{dest}.wgt'
        else:
            output_filename = dest

        logger.info(f"Creating Sky widget of {source} as {output_filename}")
        source = os.path.abspath(source)

        # Make sure the bundle is at the root of the zip
        source = source + '/'

        if not os.path.exists(source):
            logger.error("Cannot create tar - source directory does not exist")
            return False

        if os.path.exists(output_filename):
            os.remove(output_filename)

        # Build the widget
        # Start by copying all the files for the widget to a temp directory
        now = time.strftime("%Y%m%d-%H%M%S")
        tmp_dir = f'/tmp/bundlegen/{now}_{Utils.get_random_string()}'

        widget_build_dir = f'{tmp_dir}/wgt'

        shutil.copytree(source, widget_build_dir, dirs_exist_ok=True, symlinks=True, ignore_dangling_symlinks=True)
        shutil.copy('/home/vagrant/bundlegen/bundlegen/sky/resources/config.xml', widget_build_dir)
        shutil.copy('/home/vagrant/bundlegen/bundlegen/sky/resources/icon.png', widget_build_dir)

        # Zip up the contents of the widget
        shutil.make_archive(f'{tmp_dir}/temp', 'zip', widget_build_dir)

        # Sign the app and turn it into a wgt file
        logger.info("Signing Sky widget")

        command = f'/home/vagrant/bundlegen/bundlegen/sky/resources/create-sign-sky-app --skipvalid --inwgt {tmp_dir}/temp.zip --pkcs /home/vagrant/bundlegen/bundlegen/sky/resources/sky-debug-widget-cert.p12 --outwgt {output_filename}'

        # Fix a weird error by setting OPENSSL_CONF env var to point to something
        my_env = os.environ.copy()
        my_env["OPENSSL_CONF"] = "/dev/null"

        process = subprocess.Popen(shlex.split(
            command), shell=False, stdout=subprocess.PIPE, env=my_env)

        # Monitor the stdout and print to the screen
        for line in iter(process.stdout.readline, b''):
            logger.debug(line.strip().decode())

        # Process has finished, clean up and get the return code
        process.stdout.close()
        return_code = process.wait()

        # Cleanup
        shutil.rmtree(tmp_dir)

        return return_code == 0