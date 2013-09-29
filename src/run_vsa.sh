#!/bin/sh

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

set -e

export PYTHONPATH="$DIR"
echo "PYTHONPATH=$PYTHONPATH"

cd $DIR

echo "Executing VSA Daemon.."
python $DIR/vsa/daemon/vsalib.py start

echo "Executing VSA Server.."
python $DIR/vsa/model/sansrv.py start

echo "Loading configuration.."
python $DIR/vsa/client/cli/vsacli.py --load
