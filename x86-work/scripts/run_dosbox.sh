#!/bin/sh
# SPDX-License-Identifier: MIT
# Runs OPUSDOS commands in DOSBox at full speed, for checking the DOS build's
# output (not its speed), and prints their log.
#
# Usage: run_dosbox.sh <OPUSDOS.EXE> "<command>"... (run in a folder holding the media)
set -e
here="$(cd "$(dirname "$0")/.." && pwd)"
exe="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
shift
work="$(mktemp -d "$here/build/dosbox.XXXXXX")"
cp "$exe" "$work/OPUSDOS.EXE"
cp "$here"/media/*.OPU "$work/"
{
    echo "@ECHO OFF"
    for c in "$@"; do
        echo "ECHO ^> $c >> LOG.TXT"
        echo "$c >> LOG.TXT"
    done
    echo "EXIT"
} | sed 's/$/\r/' > "$work/RUN.BAT"
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy dosbox -noconsole -c "mount c $work" -c "c:" -c "RUN.BAT" -c "exit" >/dev/null 2>&1 || true
tr -d '\r' < "$work/LOG.TXT"
rm -rf "$work"
