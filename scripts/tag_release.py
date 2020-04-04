"""Tags a git tag according to what is set in owpm.owpm"""

import os
import sys
import toml


OWPM_PROJ_PATH = os.path.dirname(os.path.abspath(sys.argv[0])) + "/owpm.owpm"

with open(OWPM_PROJ_PATH, "r") as file_in:
    owpm_proj = toml.load(file_in)

proj_version = owpm_proj["version"]

print(f"Tagging owpm as version v{proj_version}..")
os.system(f"cd .. && git tag v{proj_version}")
print("Tagged, You may now commit changes!")
