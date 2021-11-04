#!/bin/bash
# Copy files for the given year from azure to cloudvps.
# To avoid out of memory errors, it copies files per month.
set -eu
YEAR=2016

# Months available in year.
# See portal.azure.com panodpanoz3mww6rxd6bjk/<YEAR>
#MONTHS=(1 2 3 4 5 6 7 8 9 10 11 12)  # 2017 and onwards.
MONTHS=(3 4 5 6 7 8 9 10 11)  # 2016 only has images in these months


for M in "${MONTHS[@]}"
do
    echo "Starting rclone for ${YEAR} ${M}..."
    LOG_FILE_STDOUT="${YEAR}_${M}.log"
    LOG_FILE_ERROR="${YEAR}_${M}.error.log"

    set -x
    nohup rclone copy --transfers 20 --checkers 20 -v azure:processed/${YEAR}/${M} cloudvps:processed/${YEAR}/${M} 2> $LOG_FILE_ERROR 1> $LOG_FILE_STDOUT
    #nohup rclone check --size-only --transfers 20 --checkers 20 azure:processed/${YEAR}/${M} cloudvps:processed/${YEAR}/${M} 2> $LOG_FILE_ERROR 1> $LOG_FILE_STDOUT
    set +x
done
