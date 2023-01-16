#!/bin/bash
#set -e

# Preprocess and analyze compressed crawl databases
EXTRACTION_DIR="/home/fsadmin/analysis2"
CENSUS_LZ4_DATA_PATH="/home/fsadmin/analysis2/census_data_lz4"
CODE_DIR="/home/fsadmin/openwpm_analysis"
ROOT_OUT_DIR="/home/fsadmin/analysis/results"
echo "DB in $EXTRACTION_DIR$NAME"
echo "Ex Dir $EXTRACTION_DIR"
echo "CENSUS LZ4 PATH $CENSUS_LZ4_DATA_PATH"
echo "out $ROOT_OUT_DIR"


declare -a urls=(
'https://webtransparency.cs.princeton.edu/webcensus/data-release/data/stateless/2016-09_1m_stateless.tar.lz4'

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
#print("already analyzed: 2017-05)


function download(){
    echo "----------------DOWNLOAD START-----------"
    echo "Downloading into $CENSUS_LZ4_DATA_PATH"
    cd $CODE_DIR
    python download_file.py $1 $CENSUS_LZ4_DATA_PATH
    echo "-----------------DOWNLOAD END-------------"
    for crawl_archive_lz4 in $CENSUS_LZ4_DATA_PATH/*.tar.lz4
	do
	echo "decompress_and_process $crawl_archive_lz4"
	decompress_and_process $crawl_archive_lz4
    done
}

function decompress_and_process(){
  echo "--------------DECOMP START------------"
  ARCHIVE_BASE_NAME=$(basename "$1")
  echo "ARCHIVE_BASE_NAME: $ARCHIVE_BASE_NAME"
  CRAWL_NAME=${ARCHIVE_BASE_NAME/.tar.lz4/}
  #CRAWL_NAME=${ARCHIVE_BASE_NAME/.lz4/}
  CRAWL_DATA_PATH=$EXTRACTION_DIR/$CRAWL_NAME
  echo "Will extract $1 to $CRAWL_DATA_PATH"
  echo "-------------EXTRACT START------------"
  time lz4 -qdc --no-sparse $1 | tar xf - -C $EXTRACTION_DIR
  exit
  cd $CODE_DIR
  echo "-------------PROCESS START------------"
  #echo "python analyze_crawl.py $CRAWL_DATA_PATH $ROOT_OUT_DIR"
  #python analyze_crawl.py $CRAWL_DATA_PATH $ROOT_OUT_DIR
  echo "python extract_features.py $CRAWL_DATA_PATH $ROOT_OUT_DIR"
  exit
  python extract_features.py $CRAWL_DATA_PATH $ROOT_OUT_DIR
  echo "Will remove $EXTRACTION_DIR/*201*"
  rm -rf $EXTRACTION_DIR/*201*
  echo "Will remove $CENSUS_LZ4_DATA_PATH/*201*"
  rm -rf $CENSUS_LZ4_DATA_PATH/*201*
}


for i in "${urls[@]}"
do echo "$i"
download "$i"
done
