{# Every Parquet file the extract wrote for one source table #}
{% macro raw_files(table_name) -%}
    read_parquet('{{ env_var("DATA_DIR", "data") }}/raw/{{ table_name }}/*.parquet')
{%- endmacro %}
