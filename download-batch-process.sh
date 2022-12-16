#!/bin/bash
#set -e

# Preprocess and analyze compressed crawl databases
EXTRACTION_DIR="/crawler/census_data_lz4/extractiondir"
CODE_DIR="/home/fsadmin/analysis/openwpm_analysis"
CENSUS_LZ4_DATA_PATH="/crawler/census_data_lz4"
ROOT_OUT_DIR="/crawler/results"
DOWNLOAD_URL_PATH="/crawler/census_data_lz4/urls.txt"

CENSUS_NORMALIZED_LZ4_DATA_PATH=${ROOT_OUT_DIR}/normalized/
mkdir -p $CENSUS_NORMALIZED_LZ4_DATA_PATH


function download(){
  echo "Downloading into $CENSUS_LZ4_DATA_PATH"
  cd $CODE_DIR
  python download_file.py $1 $EXTRACTION_DIR
}

function decompress_and_process(){
echo "Processing downloaded file..."  
ARCHIVE_BASE_NAME=$(basename "$1")
FILE_NAME="${ARCHIVE_BASE_NAME%.*}"
FULL_FILE_NAME="$EXTRACTION_DIR/*.lz4"
  
  echo "Will extract $FULL_FILE_NAME to $CRAWL_DATA_PATH"
  echo "$FILE_NAME"
  cd $EXTRACTION_DIR
  time lz4 -qdc --no-sparse $FULL_FILE_NAME > $FILE_NAME.sqlite
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
  echo "Will remove files from $EXTRACTION_DIR and $CENSUS_LZ4_DATA_PATH"
  rm -rf $EXTRACTION_DIR/*201*
  rm -rf $CENSUS_LZ4_DATA_PATH/*201*
  exit
}


while IFS= read -r line
do
	echo "$line"
  download $line
 exit
  decompress_and_process $crawl_archive_lz4
  echo "$line"

done < "$DOWNLOAD_URL_PATH"



