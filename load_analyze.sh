#!/bin/bash
#set -e

# Preprocess and analyze compressed crawl databases
EXTRACTION_DIR="/crawler/census_data_lz4/extractiondir"
CODE_DIR="/home/fsadmin/analysis/openwpm_analysis"
CENSUS_LZ4_DATA_PATH="/crawler/census_data_lz4"
ROOT_OUT_DIR="/crawler/results"
DOWNLOAD_URL_PATH="/crawler/census_data_lz4/urls.txt"
LZ4_FILE_NAME=""
CENSUS_NORMALIZED_LZ4_DATA_PATH=${ROOT_OUT_DIR}/normalized/
mkdir -p $CENSUS_NORMALIZED_LZ4_DATA_PATH


function download(){
  echo "Downloading into $CENSUS_LZ4_DATA_PATH"
  cd $CODE_DIR
  python download_file.py $1 $EXTRACTION_DIR
}

function decompress(){
  echo "Processing downloaded file..."
  cd $EXTRACTION_DIR 
  LZ4_FILE_NAME=$(find . -name "*lz4")
  FILE_NAME=${LZ4_FILE_NAME%.*} 
  echo "Will extract $LZ4_FILE_NAME"
  time lz4 -qdc --no-sparse $1 | tar xf - -C $EXTRACTION_DIR 
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
 
}

function prepare_data(){
  python process_crawl_data
}

function process(){
  cd $CODE_DIR
  python analyze_crawl.py $EXTRACTION_DIR $ROOT_OUT_DIR
}

function zip_result(){
  mkdir -p $CENSUS_NORMALIZED_LZ4_DATA_PATH/$CRAWL_NAME
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

function cleanup(){
  cd $EXTRACTION_DIR
  echo "Will remove files from $EXTRACTION_DIR and $CENSUS_LZ4_DATA_PATH"
  rm -rf $EXTRACTION_DIR/*201*
  rm -rf $CENSUS_LZ4_DATA_PATH/*201*
  exit
}


while IFS= read -r line
do
  echo "$line"
  #download $line
  #decompress
  #prepare_data
  process
  #zip_result
  #cleanup
  echo "$line"

done < "$DOWNLOAD_URL_PATH"



