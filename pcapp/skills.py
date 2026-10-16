def prepare_skill_options(catalog, defaults):
    options = list(catalog)
    catalog_by_name = {}
    for skill in options:
        catalog_by_name.setdefault(skill.casefold(), skill)

    selected = []
    selected_names = set()
    for skill in defaults:
        name = str(skill).strip()
        if not name:
            continue
        option = catalog_by_name.get(name.casefold(), name)
        option_key = option.casefold()
        if option_key not in selected_names:
            selected.append(option)
            selected_names.add(option_key)
        if option_key not in catalog_by_name:
            options.append(option)
            catalog_by_name[option_key] = option

    return options, selected
