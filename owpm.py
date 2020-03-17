"""
owpm.py
=======
The core module of owpm, used for everything apart from outside documentation/
build scripts in the scope of owpm.
"""

import hashlib
import os
import random
import shutil
import sqlite3
import subprocess
import sys
import threading
import time
from pathlib import Path
from venv import EnvBuilder

import click
import requests
import toml

BUF_SIZE = 65536  # lockfile_hash buffer size
VENV_PATH = Path(
    f"{os.path.dirname(os.path.abspath(sys.argv[0]))}/owpm_venv/"
)  # path for virtual machines


class ExceptionApiDown(Exception):
    """When a seemingly correct API request to a package repo does not return status 200"""

    pass


class ExceptionVersionError(Exception):
    """When a user gives a version of a package that is not avalible"""

    pass


class ExceptionOwpmNotFound(Exception):
    """When a detection function cannot find a .owpm file"""

    pass


class ExceptionBadOs(Exception):
    """When the user has an incompatible os. "bad os" is 100% for shortening"""

    pass


class ExceptionVenvInactive(Exception):
    """When trying to modify a venv (from [OwpmVenv]) but it is inactive/does not exist"""

    pass


class OwpmVenv:
    """A built virtual enviroment created from a valid [Project]. If no venv_pin
    is given, it will generate a new one automatically"""

    def __init__(self, venv_pin: int = None, is_active: bool = False):
        if venv_pin is None:
            self.pin = self._get_pin()
        else:
            self.pin = venv_pin

        self.path = self._get_path(self.pin)  # NOTE: could make faster
        self.is_active = is_active  # turns to True when activated

    def __repr__(self):
        return f"venv-{self.pin}"

    def create_venv(self):
        """Creates venv"""

        EnvBuilder(system_site_packages=True).create(self.path)
        self.is_active = True

    def delete(self):
        """Deletes venv if active"""

        if self.is_active and self.path.exists():
            shutil.rmtree(self.path)
            self.is_active = False
        else:
            raise ExceptionVenvInactive(
                "This venv is inactive and so cannot be deleted!"
            )

    def start_shell(self):
        """Creates an interactive shell"""

        if os.name != "posix":
            raise ExceptionBadOs("Your operating system is not currenly supported!")

        subprocess.call(
            [".", f"{self.path}/bin/activate"], shell=True
        )  # TODO: figure out permission error

    def run(self, args: list):
        """Runs given arguments inside of a temporary shell"""

        print("Coming soon..")  # TODO: finish

    def _get_path(self, pin: int) -> Path:
        """Makes a venv path from a specified PIN"""

        return VENV_PATH / str(pin)

    def _get_pin(self) -> int:
        """Randomly generates an unused PIN for a new venv"""

        for attempt in range(45):
            venv_pin = str(random.randint(0, 999))

            if not os.path.exists(self._get_path(venv_pin)):
                return venv_pin


class Project:
    """The overall project file. Name is the save name and lockfile_hash is for stopping mutliple locks on add -> install"""

    def __init__(
        self,
        name: str,
        desc: str = "No description",
        version: str = "0.1.0",
        lockfile_hash: str = "",
    ):
        self.name = name
        self.desc = desc
        self.version = version
        self.lockfile_hash = lockfile_hash
        self.packages = []

    def __repr__(self):
        return f"<name:'{self.name}', desc:'{self.desc}', version:{self.version}, packages:{len(self.packages)}>"

    def save_proj(self):
        """Creates a human-readable and editable save file"""

        save_path = Path(f"{self.name}.owpm")

        payload = {
            "desc": self.desc,
            "version": self.version,
            "lockfile_hash": self.lockfile_hash,
            "packages": {},
        }

        for package in self.packages:
            payload["packages"][package.name] = package.version

        with open(save_path, "w+") as file:
            toml.dump(payload, file)

    def lock_proj(self, force: bool = False) -> bool:
        """Locks all packages and package deps then saves to .owpmlock path;
        `force` always locks, even if owpm thinks the packages are already locked.
        Will return a False if it needed to lock or True if smart-locked"""

        lock_path = Path(f"{self.name}.owpmlock")

        if not force and lock_path.exists() and self._compare_lock_hash(lock_path):
            return True

        _del_path(lock_path)  # delete db

        conn, c = _new_lockfile_connection(lock_path)

        c.execute("CREATE TABLE lock ( name text, version text, hash text )")

        conn.commit()
        conn.close()

        # adds all deps of package
        for package in self.packages.copy():  # NOTE: also thread this potentially?
            package.get_subpackages()

        # add to db loop around
        for package in self.packages:
            lock_thread = threading.Thread(
                target=package._nthread_lock_package, args=(lock_path,)
            )
            lock_thread.start()

        time.sleep(0.5)  # race condition, wait for threading and filesystem to catch up

        self._update_lockfile_hash(lock_path)  # add new lockfile to x.owpm

        return False

    def build_proj(self) -> OwpmVenv:
        """Installs packages from lock_path, locks if lockfile is out of date and
        adds to a new venv, which is then returned for user to remember"""

        # NOTE: in the future, restructure lockfile to have primary pkgs as
        #       dependancies and make it lock *all*. Once it has, only install the
        #       primary deps with hashes and then locally check the rest

        lock_path = Path(f"{self.name}.owpmlock")

        self.lock_proj()  # ensure project is locked

        venv = OwpmVenv()
        venv.create_venv()

        conn, c = _new_lockfile_connection(lock_path)

        for dep in c.execute("SELECT * FROM lock").fetchall():
            print(f"\tInstalling '{dep[0]}':{dep[1]}..")

            # command_to_call = [
            #     f"{venv.path}/bin/python",
            #     "-m",
            #     "pip",
            #     "install",
            #     "-I",
            #     dep[0],
            #     "==",
            #     dep[1],
            #     f"--hash=md5:{dep[2]}",
            # ] # NOTE: use when versions work

            command_to_call = [
                f"{venv.path}/bin/python",
                "-m",
                "pip",
                "install",
                "-I",
                dep[0],
            ]  # NOTE: only for now

            subprocess.call(command_to_call, stdout=subprocess.DEVNULL)

        conn.close()

        return venv

    def remove_packages(self, to_remove: list):
        """Removes a list of [Package] from .owpm"""

        for package in to_remove:
            if type(package) != Package:
                raise Exception(
                    f"Trying to remove '{package}' from db which is not a [Package]!"
                )

            print(f"\tRemoving {package}")

            self.packages.remove(package)

        self.lockfile_hash = ""  # ensure lock
        self.save_proj()

    def _compare_lock_hash(self, lock_path: Path) -> bool:
        """Compares self.lockfile_hash with a newly generated hash from the actual lockfile"""

        return self._hash_lockfile(lock_path) == self.lockfile_hash

    def _hash_lockfile(self, lock_path: Path) -> str:
        """Hashes a lockfile to use in comparisons or at end of locking"""

        md5 = hashlib.md5()

        with open(lock_path, "rb") as file:
            while True:
                data = file.read(BUF_SIZE)

                if not data:
                    break

                md5.update(data)

        return md5.hexdigest()

    def _update_lockfile_hash(self, lock_path: Path):
        """Updates lockfile hash and saves it to a .owpm file (doesn't save all in self.packages)"""

        save_path = Path(f"{self.name}.owpm")

        self.lockfile_hash = self._hash_lockfile(lock_path)

        payload = toml.load(open(save_path, "r"))
        payload["lockfile_hash"] = self.lockfile_hash
        toml.dump(payload, open(save_path, "w+"))


class Package:
    """A single package when using owpm. `save_hash` is generated automatically after locking once"""

    def __init__(self, parent_proj: Project, name: str, version: str = "*"):
        self.name = name
        self.version = version
        self.parent_proj = parent_proj

        self.parent_proj.packages.append(self)
        self.parent_proj.lockfile_hash = ""

    def __repr__(self):
        return f"'{self.name}':{self.version}"

    def get_subpackages(self) -> str:
        """Scans pypi for dependancies and adds them to [Project.package] as a
        new [Package] and returns hash of this self"""

        print(f"\tPulling deps for {self}..")

        resp = _pypi_req(self.name)
        resp_json = resp.json()

        required = resp_json["info"]["requires_dist"]

        if required:  # API gives NoneType sometimes
            for subpackage in required:
                subpkg_split = subpackage.split(" ")

                if len(subpkg_split) < 2 or subpkg_split[1] == ";":
                    version = "*"
                else:
                    version = subpkg_split[1]

                # make new packages into parent [Project] and recurse
                Package(self.parent_proj, subpkg_split[0], version)

        return self.get_hash(resp)

    def get_hash(self, package_resp: requests.Response) -> str:
        """Gets lock hash, package_resp is for modularity (use `_pypi_req("package")`)"""

        resp_json = package_resp.json()

        if self.version == "*":
            return resp_json["urls"][0]["md5_digest"]

        try:
            # versions = resp_json["urls"]  # TODO: add versions, currently just * for all

            # return versions[0]["md5_digest"]

            return resp_json["urls"][0]["md5_digest"]  # NOTE: read above `TODO`
        except:
            raise ExceptionVersionError(
                f"Version {self.version} defined for package '{self.name}' is not avalible!"
            )

    def _nthread_lock_package(self, lock_path: Path):
        """Designed for a multi-threaded locking system to add a single package"""

        print(f"\tLocking {self}..")

        conn, c = _new_lockfile_connection(lock_path)

        made_hash = self.get_hash(_pypi_req(self.name))

        if c.execute(f"SELECT * FROM lock WHERE hash='{made_hash}'").fetchall():
            return  # hash already in lock, no need to add twice

        c.execute(
            f"INSERT INTO lock VALUES ( '{self.name}', '{self.version}', '{made_hash}' )"
        )

        conn.commit()
        conn.close()


def project_from_toml(owpm_path: Path) -> Project:
    """Gets a [Project] from a given TOML path"""

    payload = toml.load(open(owpm_path, "r"))

    project = Project(
        owpm_path.stem, payload["desc"], payload["version"], payload["lockfile_hash"]
    )

    for package in payload["packages"]:
        new_package = Package(project, package, payload["packages"][package])

    return project


def first_project_indir() -> Project:
    """Finds first .owpm file in running directory and returns [Project]"""

    found = False

    for file in os.listdir("."):
        if file.endswith(".owpm"):
            found = True
            return project_from_toml(Path(file))

    if not found:
        raise ExceptionOwpmNotFound("An .owpm file was not found in the current path!")


def _del_path(file_path: Path):
    """Deletes given file path if it exists"""

    if file_path.exists():
        os.remove(file_path)


def _new_lockfile_connection(lock_path: Path) -> tuple:
    """Creates a new sqlite connection to a given lockfile"""

    conn = sqlite3.connect(str(lock_path))
    c = conn.cursor()

    return (conn, c)


def _pypi_req(package: str) -> requests.Response:
    """Constructs a fully-formed json request to the PyPI API using a given
    package name"""

    resp = requests.get(f"https://pypi.org/pypi/{package}/json")

    if resp.status_code != 200:
        raise ExceptionApiDown("A seemingly valid API request to PyPI has failed!")

    return resp


@click.group()
def base_group():
    pass


@click.command()
@click.option("--name", help="Name of project", prompt="Name of your project")
@click.option("--desc", help="Breif description", prompt="Breif description/overview")
@click.option("--ver", help="Base version of project (default 0.1.0)", default="0.1.0")
def init(name, desc, ver):
    """Creates a new .owpm project file"""

    print("Initializing..")

    new_proj = Project(name, desc, ver)
    new_proj.save_proj()

    print(f"Saved project as '{name}.owpm'!")


@click.command()
@click.argument("names", nargs=-1, required=True)
def add(names):
    """Interactively adds a package to .owpm and saves .owpm"""

    print("Adding package(s)..")

    proj = first_project_indir()

    for package in names:
        new_package = Package(proj, package)
        print(f"\tAdded {new_package}!")

    proj.save_proj()

    print(f"Project saved to '{proj.name}.owpm' with {len(names)} package(s) added!")


@click.command()
@click.argument("names", nargs=-1, required=True)
def rem(names):
    """Removes provided package(s). this is interactive and may have dupe packages
    with differing versions"""

    proj = first_project_indir()
    found = []

    print("Removing package(s)..")

    removed_any_pkg = False

    for package in proj.packages:
        if package.name in names:
            found.append(
                package
            )  # TODO: make sure it doesnt delete 2 different verions with same name
            removed_any_pkg = True

    proj.remove_packages(found)

    if removed_any_pkg:
        print(f"Removed {len(found)} package(s) from '{proj.name}.owpm' and lockfile!")
    else:
        compiled_names = ", ".join(
            [f"'{name}'" for name in names]
        )  # makes tuple into `'x', 'y', 'z'`

        print(f"No packages named {compiled_names} where found so nothing was removed!")


@click.command()
@click.option(
    "--force",
    "-f",
    help="Forces a lock, even if lock is seemingly up-to-date",
    is_flag=True,
    default=False,
)
def lock(force):
    """Locks the first found .owpm file"""

    proj = first_project_indir()

    print("Locking project..")

    smart_locked = proj.lock_proj(force)

    if smart_locked:
        print(
            f"Did not lock project, '{proj.name}.owpmlock' is up-to-date! (try -f for forceful lock)"
        )
    else:
        print(f"Locked project as '{proj.name}.owpmlock'!")


@click.command()
@click.option("--pin", "-p", help="Virtual enviroment PIN", required=True)
def shell(pin):
    """Starts an interactive venv shell. Will lock if not already and create a
    venv if one is not made"""

    proj = first_project_indir()

    venv = OwpmVenv(pin)
    venv.start_shell()


@click.command()
@click.option("--pin", "-p", help="Virtual enviroment PIN", required=True)
@click.argument("args", nargs=-1)
def run(pin, args):
    """Runs provided commands inside of a temporary venv shell. Will lock if not
    already and create a venv if one is not made"""

    proj = first_project_indir()

    venv = OwpmVenv(pin)
    venv.run(args)


@click.command()
def build():
    """Constructs a new venv and provides the PIN"""

    proj = first_project_indir()

    print("Constructing new venv..")

    venv = proj.build_proj()

    print(f"Created {venv}!")


@click.command()
@click.option(
    "--pin", "-p", help="Pin wanted for removal", prompt="Pin to remove", type=int
)
def venv_rem(pin):
    """Deletes specified venv pin"""

    venv = OwpmVenv(pin, True)

    print(f"Deleting {venv}..")

    venv.delete()

    print(f"Deleted {venv}!")


@click.command()
def venv_rem_all():
    """Removes all venv files"""

    if VENV_PATH.exists():
        print("Removing all venvs..")

        shutil.rmtree(VENV_PATH)

        print("Removed all venvs!")
    else:
        print("No venvs to remove!")


@click.command()
def venv_list():
    """Lists all active venv files"""

    print("Finding venvs..")

    not_found_err = "No venvs found, you may make one using `owpm build`!"
    venv_count = 0

    if VENV_PATH.exists():
        for venv in os.listdir(VENV_PATH):
            venv_count += 1

            print(f"\t{OwpmVenv(int(venv))}")

        if venv_count == 0:
            print(not_found_err)
        else:
            print(f"Found {venv_count} venv(s)!")
    else:
        print(not_found_err)


@click.command()
def pkg_list():
    """Lists all packages of first found .owpm file"""

    proj = first_project_indir()

    if len(proj.packages) == 0:
        print("No packages added, you can add using `owpm add`!")
    else:
        print("Listing packages..")

        for package in proj.packages:
            print(f"\t{package}")

        print(f"Found {len(proj.packages)} package(s)!")


base_group.add_command(init)
base_group.add_command(lock)

base_group.add_command(add)
base_group.add_command(rem)
base_group.add_command(pkg_list)

base_group.add_command(build)
base_group.add_command(shell)  # TODO: test
base_group.add_command(run)  # TODO: test

base_group.add_command(venv_rem)
base_group.add_command(venv_rem_all)
base_group.add_command(venv_list)

if __name__ == "__main__":
    base_group()
