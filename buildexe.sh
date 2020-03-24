echo "Compiling.."
nuitka --python-version=3.6 owpm.py > /dev/null 
rm -rf owpm.build/
mkdir build/
mkdir build/owpm
mv owpm.exe build/owpm/owpm.exe
strip build/owpm.exe
echo "Compiled to ./build/owpm/!"
