#!/bin/sh
# Rebuilds mock.html from mock.src.html with the cleaned LCD plate embedded.
cd "$(dirname "$0")"
python3 -I -c "s=open('mock.src.html').read();b=open('plate.b64').read().strip();open('mock.html','w').write(s.replace('__PLATE__',b))"
