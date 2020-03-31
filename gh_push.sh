# Tool for pushing to github specifically


cd docs/
make html
cd ..

git add .

echo "Commit message:"
read cmessage

git commit -m "$cmessage"
git push
