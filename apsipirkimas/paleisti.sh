#!/bin/sh
# Paleidžia apsipirkimo programą (Mac / Linux). Langą palikite atidarytą, kol naudojatės.
cd "$(dirname "$0")" && exec python3 -m kainos.server "$@"
