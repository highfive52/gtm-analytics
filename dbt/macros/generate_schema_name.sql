{% macro generate_schema_name(custom_schema_name, node) -%}
    {# Custom schemas are literal names such as raw, src, and wh. #}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
