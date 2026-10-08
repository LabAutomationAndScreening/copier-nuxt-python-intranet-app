#!/bin/bash
set -ex

python .devcontainer/install-ci-tooling.py

# The Biome VS Code extension finds this global install; keep the version matching the biomejs/pre-commit rev in .pre-commit-config.yaml
npm install -g @biomejs/biome@2.5.15

git config --global --add --bool push.autoSetupRemote true
git config --local core.symlinks true

sh .devcontainer/create-aws-profile.sh

# ============== WARNING ==============================================================================
# File is managed by copier template: gh:LabAutomationAndScreening/copier-base-template.git
# See .config/.copier-managed-files.json for details.
#
# You are welcome to make changes to this file in your repo if they are custom to your project,
# but if the change should be shared with other projects, please backport it to the template repo.
# =====================================================================================================
