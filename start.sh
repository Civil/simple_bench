#!/bin/bash
export PYTHONPATH="$(pwd)/interactive:$(pwd)/interactive/trex:$(pwd)/interactive/trex/examples:$(pwd)/interactive/trex/examples/stl"

echo ${PYTHONPATH}
python3 -msimple_bench -r 5mpps
