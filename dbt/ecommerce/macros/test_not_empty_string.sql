{% test not_empty_string(model, column_name) %}

select
    {{ column_name }}
from {{ model }}
where {{ column_name }} = ''
   or ({{ column_name }} is not null and trim({{ column_name }}) = '')

{% endtest %}
