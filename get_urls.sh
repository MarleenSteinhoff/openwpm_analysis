#!/bin/bash
#set -e

# Preprocess and analyze compressed crawl databases
EXTRACTION_DIR="/tmp/census_tmp"
BASE_PATH_HS="/home/mfuchs"
BASE_PATH_FS="/crawler"
CENSUS_LZ4_DATA_PATH="/crawler/analysis/census_data_lz4"
CODE_DIR="/crawler/openwpm_analysis"
ROOT_OUT="/crawler/results"

echo "Ex Dir $EXTRACTION_DIR"
echo "CENSUS LZ4 PATH $CENSUS_LZ4_DATA_PATH"
echo "out $ROOT_OUT"


declare -a urls_1=(
        "https://webtransparency.cs.princeton.edu/webcensus/data-release/data/stateless/2017-06_1m_stateless.tar.lz4"
        "https://webtransparency.cs.princeton.edu/webcensus/data-release/data/stateless/2017-07_1m_stateless.tar.lz4"
        "https://webtransparency.cs.princeton.edu/webcensus/data-release/data/stateless/2017-09_1m_stateless.tar.lz4"
        "https://webtransparency.cs.princeton.edu/webcensus/data-release/data/stateless/2017-10_1m_stateless.tar.lz4"
        "https://webtransparency.cs.princeton.edu/webcensus/data-release/data/stateless/2017-12_1m_stateless.tar.lz4"
        "https://webtransparency.cs.princeton.edu/webcensus/data-release/data/stateless/2018-01_1m_stateless.tar.lz4"
        "https://webtransparency.cs.princeton.edu/webcensus/data-release/data/stateless/2018-02_1m_stateless.tar.lz4"
        "https://webtransparency.cs.princeton.edu/webcensus/data-release/data/stateless/2018-03_1m_stateless.tar.lz4"
        "https://webtransparency.cs.princeton.edu/webcensus/data-release/data/stateless/2018-06_1m_stateless.tar.lz4"
        "https://webtransparency.cs.princeton.edu/webcensus/data-release/data/stateless/2018-11_1m_stateless.tar.lz4"
        "https://webtransparency.cs.princeton.edu/webcensus/data-release/data/stateless/2019-06_1m_stateless.tar.lz4")
declare -a urls_2=(
        "https://webtransparency.cs.princeton.edu/webcensus/data-release/data/stateless/2015-12_1m_stateless.tar.lz4"
        "https://webtransparency.cs.princeton.edu/webcensus/data-release/data/stateless/2016-03_1m_stateless.tar.lz4"
        "https://webtransparency.cs.princeton.edu/webcensus/data-release/data/stateless/2016-04_1m_stateless.tar.lz4"
        "https://webtransparency.cs.princeton.edu/webcensus/data-release/data/stateless/2016-05_1m_stateless.tar.lz4"
        "https://webtransparency.cs.princeton.edu/webcensus/data-release/data/stateless/2016-06_1m_stateless.tar.lz4"
        "https://webtransparency.cs.princeton.edu/webcensus/data-release/data/stateless/2016-07_1m_stateless.tar.lz4"
        "https://webtransparency.cs.princeton.edu/webcensus/data-release/data/stateless/2016-08_1m_stateless.tar.lz4"
        "https://webtransparency.cs.princeton.edu/webcensus/data-release/data/stateless/2016-09_1m_stateless.tar.lz4"
        "https://webtransparency.cs.princeton.edu/webcensus/data-release/data/stateless/2017-01_1m_stateless.tar.lz4"
        "https://webtransparency.cs.princeton.edu/webcensus/data-release/data/stateless/2017-02_1m_stateless.tar.lz4"
        "https://webtransparency.cs.princeton.edu/webcensus/data-release/data/stateless/2017-03_1m_stateless.tar.lz4"
        "https://webtransparency.cs.princeton.edu/webcensus/data-release/data/stateless/2017-04_1m_stateless.tar.lz4"
        "https://webtransparency.cs.princeton.edu/webcensus/data-release/data/stateless/2017-05_1m_stateless.tar.lz4")


function download(){
    echo "Downloading into $CENSUS_LZ4_DATA_PATH"
    cd $CODE_DIR
    python download_file.py $1 $CENSUS_LZ4_DATA_PATH
    for crawl_archive_lz4 in $CENSUS_LZ4_DATA_PATH/*.tar.lz4
        do decompress_and_process $crawl_archive_lz4 $1
    done
}

function decompress_and_process(){
  ARCHIVE_BASE_NAME=$(basename "$1")
  echo $ARCHIVE_BASE_NAME
  CRAWL_NAME=${ARCHIVE_BASE_NAME/.tar.lz4/}
  CRAWL_DATA_PATH=$EXTRACTION_DIR/$CRAWL_NAME
  echo "Will extract $1 to $CRAWL_DATA_PATH"
  time lz4 -qdc --no-sparse $1 | tar xf - -C $EXTRACTION_DIR
  python process_crawl_data.py $CRAWL_DATA_PATH $ROOT_OUT_DIR
  echo "Size before vacuuming"
  ls -hl $EXTRACTION_DIR/*201*/201*.sqlite
  time sqlite3 $EXTRACTION_DIR/*201*/*201*.sqlite 'PRAGMA journal_mode = OFF; PRAGMA synchronous = OFF; PRAGMA page_size = 32768; VACUUM;'
  echo "Size after vacuuming"
  ls -hl $EXTRACTION_DIR/*201*/*201*.sqlite
  echo "Start getting urls with"
  echo "python process_crawl_data.py $CRAWL_DATA_PATH $ROOT_OUT_DIR"
  python analyze_crawl.py $CRAWL_DATA_PATH $ROOT_OUT_DIR
}


for i in "${urls_1[@]}"
do echo "$i"
download "$i"  
done
