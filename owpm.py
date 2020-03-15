from pathlib import Path
import toml
import click
import hashlib
import sqlite3
import os
import requests
import threading
import time

BUF_SIZE = 65536  # lockfile_hash buffer size


class ExceptionApiDown(Exception):
    """When a seemingly correct API request to a package repo does not return status 200"""

    pass


class ExceptionVersionError(Exception):
    """When a user gives a version of a package that is not avalible"""

    pass


class ExceptionOwpmNotFound(Exception):
    """When a detection function cannot find a .owpm file"""

    pass


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
        for package in self.packages.copy():
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

    def install_packages(self):
        """Installs packages from lock_path, locks if lockfile is out of date and adds to active venv"""

        lock_path = Path(f"{self.name}.owpmlock")
        lock_packages = []  # in format [{name, version, hash}] instead of in a class

        if not lock_path.exists() or self._compare_lock_hash(lock_path) is False:
            self.lock_proj()  # locks project if lockfile is out of date or doesn't exist

        conn = sqlite3.connect(str(lock_path))
        c = conn.cursor()

        for item in c.execute("SELECT * FROM lock").fetchall():
            print(item)

        conn.close()

        # TODO: install to active venv

    def remove_packages(self, to_remove: list):
        """Removes a list of [Package] from .owpm, lockfile and current active venv"""

        for package in to_remove:
            if type(package) != Package:
                raise Exception(
                    f"Trying to remove '{package}' from db which is not a [Package]!"
                )

            self.packages.remove(to_remove)

        self.save_proj()
        self.lock_proj()

        # TODO: remove from active venv

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

    def __repr__(self):
        return f"'{self.name}':{self.version}"

    def get_subpackages(self) -> str:
        """Scans pypi for dependancies and adds them to [Project.package] as a
        new [Package] and returns hash of this self"""

        resp = pypi_req(self.name)
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
        """Gets lock hash, package_resp is for modularity (use `pypi_req("package")`)"""

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

        made_hash = self.get_hash(pypi_req(self.name))

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


def pypi_req(package: str) -> requests.Response:
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
@click.argument("names", nargs=-1)
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
@click.argument("names", nargs=-1)
def rem(names):
    """Removes a given package, this is interactive and may have dupe packages
    with differing versions"""

    print("Removing package(s)..")

    proj = first_project_indir()
    found = []

    for package in proj.packages:
        if package.name in names:
            found.append(
                package
            )  # TODO: make sure it doesnt delete 2 different verions with same name

    proj.remove_packages(found)

    print(
        f"Removed '{picked_pkg.name}':{picked_pkg.version} from .owpm, lockfile and active venv!"
    )


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

    if force:
        print("Forcefully locking project..")
    else:
        print("Locking project..")

    proj = first_project_indir()

    smart_locked = proj.lock_proj(force)

    if smart_locked:
        print(
            f"Did not lock project, '{proj.name}.owpmlock' is up-to-date! (try -f for forceful lock)"
        )
    else:
        print(f"Locked project as '{proj.name}.owpmlock'!")


base_group.add_command(init)
base_group.add_command(add)
base_group.add_command(rem)  # TODO fix
base_group.add_command(lock)

if __name__ == "__main__":
    base_group()
