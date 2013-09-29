#!/bin/bash

set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

cd ..
export PYTHONPATH=`pwd`

python $DIR/vsa_redirect_callback.pyc $1 $2
