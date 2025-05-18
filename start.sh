#!/bin/bash
export PYTHONPATH="$(pwd)/interactive:$(pwd)/interactive/trex:$(pwd)/interactive/trex/examples:$(pwd)/interactive/trex/examples/stl"
export TREX_EXT_LIBS="$(pwd)/external_libs"
export STL_PROFILES_PATH="$(pwd)/profiles"
echo ${PYTHONPATH}
python3 -msimple_bench -t $((300*1000)) -b 10000 -s 50
