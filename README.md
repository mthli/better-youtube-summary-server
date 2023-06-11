# better-youtube-summary-server

Literally Better YouTube Summary 🎯

**UNDER DEVELOPMENT.**

## Development

Currently this project is developed on **macOS 13.3 (22E252).**

But this project **can't run on macOS** actually, just for coding.

First install dependencies as follow:

```bash
# Install 'redis' if you don't have.
# https://redis.io/docs/getting-started/installation/install-redis-on-mac-os
brew install redis
brew services start redis

# Install 'python3' if you don't have.
brew install python3

# Install 'pyenv' if you don't have.
# https://github.com/pyenv/pyenv#automatic-installer
curl https://pyenv.run | bash

# Install 'pipenv' if you don't have.
pip3 install --user pipenv

# Install all dependencies needed by this project.
pipenv install
pipenv install --dev
```

Then just open you editor and have fun.

## Deployment

This project should be deployed to **Debian GNU/Linux 11 (bullseye).**

First install dependencies as follow:

```bash
# Install 'nginx' if you don't have.
sudo apt-get install nginx
sudo systemd enable nginx
sudo systemd start nginx

# Install 'redis' if you don't have.
sudo apt-get install redis
sudo systemd enable redis
sudo systemd start redis

# Install 'certbot' if you don't have.
sudo apt-get install certbot
sudo apt-get install python3-certbot-nginx

# Install 'pm2' if you don't have.
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.3/install.sh | bash
nvm install node # restart your bash, then
npm install -g pm2
pm2 install pm2-logrotate

# Install 'python3' if you don't have.
sudo apt-get install python3
sudo apt-get install python3-pip

# Install 'pyenv' if you don't have.
# https://github.com/pyenv/pyenv#automatic-installer
curl https://pyenv.run | bash

# Install 'pipenv' if you don't have.
pip install --user pipenv

# Install all dependencies needed by this project.
pipenv install
pipenv install --dev
```

Before run this project:

- Set `openai_api_key` defined in `./rds.py` with `redis-cli`
- TODO

Then just execute commands as follow:

```bash
# Make sure you are not in pipenv shell.
pm2 start ./pm2.json
```

## License

```
better-youtube-summary-server - Literally Better YouTube Summary.

Copyright (C) 2023  Matthew Lee

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published
by the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
```
