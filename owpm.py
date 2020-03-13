from pathlib import Path
import toml
import click
import hashlib
import sqlite3
import os

BUF_SIZE = 65536  # lockfile_hash buffer size


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

    def lock_proj(self):
        """Locks all packages and package deps then saves to .owpmlock path"""

        lock_path = Path(f"{self.name}.owpmlock")
        _del_path(lock_path)  # delete db

        conn = sqlite3.connect(str(lock_path))
        c = conn.cursor()

        c.execute("CREATE TABLE lock ( name text, version text, hash text )")

        # adds all deps of package
        for package in self.packages:
            package.get_subpackages()

        # add to db loop around
        for package in self.packages:
            made_hash = (
                package.get_hash()
            )  # NOTE will not work until [Package.get_hash] works

            if not made_hash:
                _del_path(lock_path)  # delete db

                raise Exception(
                    f"No lock hash found for package '{package.name}' with version `{package.version}`!"
                )
            elif c.execute(f"SELECT * FROM lock WHERE hash='{made_hash}'").fetchall():
                continue  # hash already in lock, no need to add twice

            c.execute(
                f"INSERT INTO lock VALUES ( '{package.name}', '{package.version}', '{made_hash}' )"
            )

        conn.commit()
        conn.close()

        self.lockfile_hash = self._hash_lockfile(
            lock_path
        )  # add new lockfile to self.lockfile_hash

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


class Package:
    """A single package when using owpm. `save_hash` is generated automatically after locking once"""

    def __init__(self, parent_proj: Project, name: str, version: str = "*"):
        self.name = name
        self.version = version

        parent_proj.packages.append(self)

    def __repr__(self):
        return f"<name:'{self.name}', version:'{self.version}'>"

    def get_subpackages(self):
        """Scans pypi for dependancies and adds them to [Project.package] as a new [Package]"""

        pass

    def get_hash(self) -> str:
        """Gets lock hash"""

        pass


def project_from_toml(owpm_path: Path) -> Project:
    """Gets a [Project] from a given TOML path"""

    payload = toml.load(open(owpm_path, "r"))

    project = Project(
        owpm_path.stem, payload["desc"], payload["version"], payload["lockfile_hash"]
    )

    for package in payload["packages"]:
        new_package = Package(project, package, payload["packages"][package])

    return project


def _del_path(file_path: Path):
    """Deletes given file path if it exists"""

    if file_path.exists():
        os.remove(file_path)


@click.group()
def base_group():
    """The owpm CLI"""

    pass


if __name__ == "__main__":
    got_proj = project_from_toml(Path("owpm.owpm"))
    new_package = Package(got_proj, "click")
    got_proj.save_proj()
    got_proj.install_packages()

    base_group()
