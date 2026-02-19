import pyarrow as pa
import pyarrow.parquet as pq


def save_array_to_parquet(data_2d, output_path):

    flattened = data_2d.flatten()
    
    # Create a table with N rows, one double value per row
    table = pa.table({"data": pa.array(flattened, type=pa.float64())})


    pq.write_table(table, output_path, compression='gzip', version='2.4', flavor='none', data_page_size =None, encryption_properties=None)
