#!/bin/bash
#set -e

# Preprocess and analyze compressed crawl databases
EXTRACTION_DIR="/crawler/analysis"
BASE_PATH_HS="/home/mfuchs"
BASE_PATH_FS="/crawler"
CENSUS_LZ4_DATA_PATH="/crawler/analysis/census_data_lz4"
CODE_DIR="/crawler/openwpm_analysis"
ROOT_OUT_DIR="/crawler/results"

echo "Ex Dir $EXTRACTION_DIR"
echo "CENSUS LZ4 PATH $CENSUS_LZ4_DATA_PATH"
echo "out $ROOT_OUT"


declare -a urls_1=(
        'https://webtransparency.cs.princeton.edu/webcensus/data-release/data/stateless/2018-06_1m_stateless.tar.lz4'
        'https://webtransparency.cs.princeton.edu/webcensus/data-release/data/stateless/2016-05_1m_stateless.tar.lz4'
         'https://webtransparency.cs.princeton.edu/webcensus/data-release/data/stateless/2018-11_1m_stateless.tar.lz4'
         'https://webtransparency.cs.princeton.edu/webcensus/data-release/data/stateless/2016-04_1m_stateless.tar.lz4'
        'https://webtransparency.cs.princeton.edu/webcensus/data-release/data/stateless/2016-07_1m_stateless.tar.lz4'
        'https://webtransparency.cs.princeton.edu/webcensus/data-release/data/stateless/2016-09_1m_stateless.tar.lz4'
        'https://webtransparency.cs.princeton.edu/webcensus/data-release/data/stateless/2017-02_1m_stateless.tar.lz4'
         'https://webtransparency.cs.princeton.edu/webcensus/data-release/data/stateless/2017-04_1m_stateless.tar.lz4'
         'https://webtransparency.cs.princeton.edu/webcensus/data-release/data/stateless/2017-07_1m_stateless.tar.lz4'
          'https://webtransparency.cs.princeton.edu/webcensus/data-release/data/stateless/2017-10_1m_stateless.tar.lz4'
          'https://webtransparency.cs.princeton.edu/webcensus/data-release/data/stateless/2018-01_1m_stateless.tar.lz4'
)

declare -a urls_2=(
        'https://webtransparency.cs.princeton.edu/webcensus/data-release/data/stateless/2019-06_1m_stateless.tar.lz4'
      'https://webtransparency.cs.princeton.edu/webcensus/data-release/data/stateless/2017-05_1m_stateless.tar.lz4'
       'https://webtransparency.cs.princeton.edu/webcensus/data-release/data/stateless/2016-03_1m_stateless.tar.lz4'
        'https://webtransparency.cs.princeton.edu/webcensus/data-release/data/stateless/2016-06_1m_stateless.tar.lz4'
       'https://webtransparency.cs.princeton.edu/webcensus/data-release/data/stateless/2016-08_1m_stateless.tar.lz4'
        'https://webtransparency.cs.princeton.edu/webcensus/data-release/data/stateless/2017-01_1m_stateless.tar.lz4'
         'https://webtransparency.cs.princeton.edu/webcensus/data-release/data/stateless/2017-03_1m_stateless.tar.lz4'
        'https://webtransparency.cs.princeton.edu/webcensus/data-release/data/stateless/2017-06_1m_stateless.tar.lz4'
      'https://webtransparency.cs.princeton.edu/webcensus/data-release/data/stateless/2017-09_1m_stateless.tar.lz4'
        'https://webtransparency.cs.princeton.edu/webcensus/data-release/data/stateless/2017-12_1m_stateless.tar.lz4'
       'https://webtransparency.cs.princeton.edu/webcensus/data-release/data/stateless/2018-02_1m_stateless.tar.lz4'
       'https://webtransparency.cs.princeton.edu/webcensus/data-release/data/stateless/2018-03_1m_stateless.tar.lz4'
)

declare -a url_table=(
  'https://webtransparency.cs.princeton.edu/webcensus/data-release/data/stateless/2016-05_1m_stateless.tar.lz4'
  'https://webtransparency.cs.princeton.edu/webcensus/data-release/data/stateless/2017-01_1m_stateless.tar.lz4'
 'https://webtransparency.cs.princeton.edu/webcensus/data-release/data/stateless/2018-06_1m_stateless.tar.lz4'

)

function download(){
    echo "Downloading into $CENSUS_LZ4_DATA_PATH"
    cd $CODE_DIR
    python download_file.py $1 $CENSUS_LZ4_DATA_PATH
    for crawl_archive_lze in $CENSUS_LZ4_DATA_PATH/*.lz4
    #for crawl_archive_lz4 in $CENSUS_LZ4_DATA_PATH/*.tar.lz4
        do decompress_and_process $crawl_archive_lz4 $1
    done
}

function decompress_and_process(){
  echo "--------------DECOMP START------------"
  ARCHIVE_BASE_NAME=$(basename "$1")
  echo "ARCHIVE_BAS_NAME: $ARCHIVE_BASE_NAME"
  #CRAWL_NAME=${ARCHIVE_BASE_NAME/.tar.lz4/}
  CRAWL_NAME=${ARCHIVE_BASE_NAME/.lz4/}
  CRAWL_DATA_PATH=$EXTRACTION_DIR/$CRAWL_NAME
  echo "Will extract $ARCHIVE_BASE_NAME to $EXTRACTION_DIR"
  echo "-------------EXTRACT START------------"
  cd $CENSUS_LZ4_DATA_PATH
  #time lz4 -qdc --no-sparse $1 | tar xf - -C $EXTRACTION_DIR
  echo "time lz4 -qdc --no-sparce $ARCHIVE_BASE_NAME > $CRAWL_DATA_PATH"
  time lz4 -qdc --no-sparse $ARCHIVE_BASE_NAME > $CRAWL_DATA_PATH
  cd $CODE_DIR
  echo "-------------PROCESS START------------"
  echo "python analyze_crawl.py $EXTRACTION_DIR $ROOT_OUT_DIR"
  python analyze_crawl.py $EXTRACTION_DIR $ROOT_OUT_DIR
  echo "Will remove $EXTRACTION_DIR/*201*"
  rm -rf $EXTRACTION_DIR/*201*
  echo "Will remove $CENSUS_LZ4_DATA_PATH/*201*"
  rm -rf $CENSUS_LZ4_DATA_PATH/*201*
}


for i in "${urls_1[@]}"
do echo "$i"
download "$i"  
done
