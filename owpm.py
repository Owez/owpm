from pathlib import Path
import toml
import click
import hashlib

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

    def init_proj(self, save_path: Path):
        """Creates a human-readable and editable save file"""

        payload = {
            "desc": self.desc,
            "version": self.version,
            "lockfile_hash": self.lockfile_hash,
            packages: [],
        }

        for package in self.packages:
            payload["packages"].append(package.save_representation())

        with open(save_path, "w") as file:
            toml.dump(payload, file)

    def lock_proj(self, lock_path: Path):
        """Locks all packages and package deps then saves to .owpmlock path"""

        # TODO: make all of this a sqlite3 db and have it add hashed new lockfile to self.lockfile_hash at end

        # adds all deps of package
        for package in self.packages.copy():
            package.get_subpackages()

        self.lockfile_hash = self._hash_lockfile(
            lock_path
        )  # NOTE: put this at end when finished updates

        pass

        # payload = {
        #     lock_packages: [],
        # }

        # # now locks all fully-added packages
        # for package in self.packages:
        #     payload["packages"].append(package.lock()) # NOTE: with sqlite3 prep, .lock() now just returns hash

        # with open(save_path, "r") as file:
        #     toml.dump(payload, file)

    def install_packages(self, lock_path: Path):
        """Installs packages from lock_path and locks if lockfile is out of date"""

        lock_packages = []  # in format [{name, version, hash}] instead of in a class

        if self._compare_lock_hash(lock_path) is False:
            self.lock_proj()  # locks project if lockfile is out of date

        pass  # TODO: loop through and install all

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

    def get_subpackages(self):
        """Scans pypi for dependancies and adds them to [Project.package] as a new [Package]"""

        pass

    def lock(self) -> str:
        """Gets lock hash"""

        pass

    def save_representation(self) -> dict:
        """User-friendly toml representation of package as dict"""

        return {
            "name": self.name,
            "version": self.version,
        }


def project_from_toml(owpm_path: Path) -> Project:
    """Gets a [Project] from a given TOML path"""

    payload = toml.load(open(owpm_path, "r"))

    project = Project(
        owpm_path.stem, payload["desc"], payload["version"], payload["lockfile_hash"]
    )

    for package in payload["packages"]:
        new_package = Package(
            project,
            payload["packages"][package]["name"],
            payload["packages"][package]["version"],
        )
        project.packages.append(new_package)

    return project


@click.group()
def base_group():
    """The owpm CLI"""

    pass


if __name__ == "__main__":
    project_from_toml(Path("owpm.toml"))
    base_group()
