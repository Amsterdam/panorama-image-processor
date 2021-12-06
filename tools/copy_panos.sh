#!/bin/bash
# Copy files for the given year from azure to cloudvps.
# To avoid out of memory errors, it copies files per month.
set -eux
YEAR=2017

# Months available in year.
# See portal.azure.com panodpanoz3mww6rxd6bjk/<YEAR>
MONTHS=(01 02 03 04 05 06 07 08 09 10 11 12)

for M in "${MONTHS[@]}"
do
    echo "Starting rclone for ${YEAR} ${M}..."
    LOG_FILE_STDOUT="${YEAR}_${M}.log"
    LOG_FILE_ERROR="${YEAR}_${M}.error.log"

    nohup rclone copy --transfers 20 --checkers 20 -v azure:processed/${YEAR}/${M} cloudvps:processed/${YEAR}/${M} 2> $LOG_FILE_ERROR 1> $LOG_FILE_STDOUT
    #nohup rclone check --size-only --transfers 20 --checkers 20 azure:processed/${YEAR}/${M} cloudvps:processed/${YEAR}/${M} 2> $LOG_FILE_ERROR 1> $LOG_FILE_STDOUT
done
