#!/bin/bash
#set -e

# Preprocess and analyze compressed crawl databases
EXTRACTION_DIR="/tmp/census_tmp"

CENSUS_LZ4_DATA_PATH="/tmp/census_data_lz4"
ROOT_OUT_DIR="/crawler/results"

CENSUS_NORMALIZED_LZ4_DATA_PATH=${ROOT_OUT_DIR}/normalized/
mkdir -p $CENSUS_NORMALIZED_LZ4_DATA_PATH

urls=' "https://webtransparency.cs.princeton.edu/webcensus/data-release/data/stateless/2015-12_1m_stateless.tar.lz4"
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
        "https://webtransparency.cs.princeton.edu/webcensus/data-release/data/stateless/2017-05_1m_stateless.tar.lz4"
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
        "https://webtransparency.cs.princeton.edu/webcensus/data-release/data/stateless/2019-06_1m_stateless.tar.lz4"'


function decompress_and_process(){
  echo "Downloading file to process..."
  ARCHIVE_BASE_NAME=$(basename "$1")
  CRAWL_NAME=${ARCHIVE_BASE_NAME.tar.lz4}
  CRAWL_DATA_PATH=$EXTRACTION_DIR/$CRAWL_NAME
  echo "Will extract $1 to $CRAWL_DATA_PATH"
  time lz4 -qdc --no-sparse $1 | tar xf - -C $EXTRACTION_DIR
  python process_crawl_data.py $CRAWL_DATA_PATH $ROOT_OUT_DIR
  echo "Size before vacuuming"
  ls -hl $EXTRACTION_DIR/*201*/201*.sqlite
  time sqlite3 $EXTRACTION_DIR/*201*/*201*.sqlite 'PRAGMA journal_mode = OFF; PRAGMA synchronous = OFF; PRAGMA page_size = 32768; VACUUM;'
  echo "Size after vacuuming"
  ls -hl $EXTRACTION_DIR/*201*/*201*.sqlite
  python analyze_crawl.py $CRAWL_DATA_PATH $ROOT_OUT_DIR

  mkdir -p $CENSUS_NORMALIZED_LZ4_DATA_PATH/$2
  OUT_NORMALIZED_ARCHIVE=$EXTRACTION_DIR/$ARCHIVE_BASE_NAME
  pushd .
  cd $EXTRACTION_DIR
  tar c *201* | lz4 -9zq - $OUT_NORMALIZED_ARCHIVE
  popd
  scp $OUT_NORMALIZED_ARCHIVE odin://mnt/10tb2/census-release-normalized/$2/
  rm $OUT_NORMALIZED_ARCHIVE
  echo "Will remove $EXTRACTION_DIR/*201*"
  rm -rf $EXTRACTION_DIR/*201*
}


for crawl_archive_lz4 in $CENSUS_LZ4_DATA_PATH/$1/*.tar.lz4
  do decompress_and_process $crawl_archive_lz4 $1
done;


