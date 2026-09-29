"""Validate the declarative schema's used keywords without adding runtime dependencies."""

def validate_schema(value,schema,path='$'):
    if 'const' in schema and (value!=schema['const'] or type(value)!=type(schema['const'])):raise ValueError(path+': const')
    if 'enum' in schema and value not in schema['enum']:raise ValueError(path+': enum')
    if 'type' in schema:
        names=schema['type'] if isinstance(schema['type'],list) else [schema['type']]
        checks={'object':lambda:isinstance(value,dict),'array':lambda:isinstance(value,list),'string':lambda:isinstance(value,str),'boolean':lambda:type(value) is bool,'integer':lambda:type(value) is int,'number':lambda:type(value) in (int,float),'null':lambda:value is None}
        if not any(checks[n]() for n in names):raise ValueError(path+': type')
    if isinstance(value,dict):
        for key in schema.get('required',[]):
            if key not in value:raise ValueError(path+': missing '+key)
        properties=schema.get('properties',{})
        if schema.get('additionalProperties') is False and set(value)-set(properties):raise ValueError(path+': extra properties')
        for key,child in value.items():
            if key in properties:validate_schema(child,properties[key],path+'.'+key)
    if isinstance(value,list) and 'items' in schema:
        for index,child in enumerate(value):validate_schema(child,schema['items'],path+f'[{index}]')
