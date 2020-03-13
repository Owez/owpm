echo "Compiling.."
nuitka --python-version=3.6 owpm.py > /dev/null 
rm -rf owpm.build/
mkdir build/
mv owpm.exe build/owpm.exe
echo "Compiled to ./build/owpm.exe!"
