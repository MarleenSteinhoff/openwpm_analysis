#!/bin/bash
#set -e

# Preprocess and analyze compressed crawl databases
EXTRACTION_DIR="/crawler/census_data_lz4/extractiondir"
CODE_DIR="/home/fsadmin/analysis/openwpm_analysis"
CENSUS_LZ4_DATA_PATH="/crawler/census_data_lz4"
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
echo "Processing downloaded file..."  
ARCHIVE_BASE_NAME=$(basename "$1")
  FILE_NAME="${ARCHIVE_BASE_NAME%.*}"
  
  echo "Will extract $1 to $CRAWL_DATA_PATH"
  echo "$FILE_NAME"
  cd $EXTRACTION_DIR
  time lz4 -qdc --no-sparse $1 > $FILE_NAME.sqlite
  rm -f *.lz4
  #time lz4 -qdc --no-sparse $1 | tar xf - -C $EXTRACTION_DIR
  echo "File successfully extracted"
  #only if crawl is new
  #python process_crawl_data.py $EXTRACTION_DIR/$CRAWL_NAME $ROOT_OUT_DIR
  echo "Size before vacuuming"
  ls -hl $EXTRACTION_DIR/*.sqlite
  time sqlite3 $EXTRACTION_DIR/*.sqlite 'PRAGMA journal_mode = OFF; PRAGMA synchronous = OFF; PRAGMA page_size = 32768; VACUUM;'
  echo "Size after vacuuming"
  ls -hl $EXTRACTION_DIR/*.sqlite
  cd $CODE_DIR
  python analyze_crawl.py $EXTRACTION_DIR $ROOT_OUT_DIR
  mkdir -p $CENSUS_NORMALIZED_LZ4_DATA_PATH/$CRAWL_NAME
  OUT_NORMALIZED_ARCHIVE=$EXTRACTION_DIR/$ARCHIVE_BASE_NAME
  cd $EXTRACTION_DIR
  echo "SUCCESS!"
  echo "Will remove files from $EXTRACTION_DIR and $CENSUS_LZ4_DATA_PATH"
  rm -rf $EXTRACTION_DIR/*201*
  rm -rf $CENSUS_LZ4_DATA_PATH/*201*
  
}


for crawl_archive_lz4 in $CENSUS_LZ4_DATA_PATH/*.lz4
  do decompress_and_process $crawl_archive_lz4 $1
done;
