[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white)](https://github.com/pre-commit/pre-commit)
[![Copier](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/copier-org/copier/master/img/badge/badge-black.json)](https://github.com/copier-org/copier)
[![Actions status](https://www.github.com/LabAutomationAndScreening/copier-nuxt-python-intranet-app/actions/workflows/ci.yaml/badge.svg?branch=main)](https://www.github.com/LabAutomationAndScreening/copier-nuxt-python-intranet-app/actions)
[![Open in Dev Containers](https://img.shields.io/static/v1?label=Dev%20Containers&message=Open&color=blue)](https://vscode.dev/redirect?url=vscode://ms-vscode-remote.remote-containers/cloneInVolume?url=https://www.github.com/LabAutomationAndScreening/copier-nuxt-python-intranet-app)
[![OpenIssues](http://isitmaintained.com/badge/open/LabAutomationAndScreening/copier-nuxt-python-intranet-app.svg)](http://isitmaintained.com/project/LabAutomationAndScreening/copier-nuxt-python-intranet-app)

# Usage
To create a new repository using this template:
1. Create a basic devcontainer either using the Codespaces default or using the file `.devcontainer/devcontainer-to-instantiate-template.json` from [the base template repo](https://github.com/LabAutomationAndScreening/copier-base-template/blob/main/.devcontainer/devcontainer-to-instantiate-template.json)
1. Inside that devcontainer, run `python .devcontainer/install-ci-tooling.py` to install necessary tooling to instantiate the template (you can copy/paste the script from this repo...and you can paste it in the root of the repo if you want)
1. Delete all files currently in the repository. Optional...but makes it easiest to avoid git conflicts.
1. Run copier to instantiate the template: `copier copy --trust gh:LabAutomationAndScreening/copier-nuxt-python-intranet-app.git .`
1. Run `python .devcontainer/manual-setup-deps.py --only-create-lock --allow-uv-to-install-python` to generate the lock file(s)
1. Stage all files to prepare for commit (`git add .`)
1. Run `python3 .github/workflows/hash_git_files.py . --for-devcontainer-config-update` to update the hash for your devcontainer file
1. Commit the changes (optional)
1. Rebuild your new devcontainer



# Development

## Obtaining the GraphiQL files to bundle
1. Navigate into the static folder: `cd "template/{% if has_backend %}backend{% endif %}/src/static/{% if frontend_uses_graphql %}static{% endif %}/graphiql"`
1. Confirm by viewing the source of a non-altered GraphiQL page that these are the files to download
1. `curl https://unpkg.com/react@18.2.0/umd/react.production.min.js > react.production.min.js`
1. `curl https://unpkg.com/react-dom@18.2.0/umd/react-dom.production.min.js > react-dom.production.min.js`
1. `curl https://unpkg.com/js-cookie@3.0.5/dist/js.cookie.min.js > js.cookie.min.js`
1. `curl https://unpkg.com/graphiql@3.8.3/graphiql.min.css > graphiql.min.css`
1. `curl https://unpkg.com/@graphiql/plugin-explorer@1.0.2/dist/style.css > style.css`
1. `curl https://unpkg.com/graphiql@3.8.3/graphiql.min.js > graphiql.min.js`
1. `curl https://unpkg.com/@graphiql/plugin-explorer@1.0.2/dist/index.umd.js > index.umd.js`

## Updating from the template
This repository uses a copier template. To pull in the latest updates from the template, use the command:
`copier update --trust --conflict rej --defaults`
