# Generic template

git clone https://github.com/username/template-repo.git
mv template-repo new-project-name
cd new-project-name
rm -rf .git
git init
git add .
git commit -m "Initial commit from template"
git remote add origin https://github.com/username/new-project-name.git
git push -u origin main
