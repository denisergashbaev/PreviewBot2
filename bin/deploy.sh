Please use PyCharm so that we have the same PEP8-based formatting

See [wiki](https://github.com/denisergashbaev/PreviewBot/wiki/)
#!/usr/bin/env bash
echo "deploying.."
./activate-virtualenv.sh
./install-requirements.sh
/etc/init.d/preview-bot restart