# Creating Plugins for changedetection.io

This document describes how to create plugins for changedetection.io. Plugins can be used to extend the functionality of the application in various ways.

## Plugin Types

### UI Stats Tab Plugins

These plugins can add content to the Stats tab in the Edit page. This is useful for adding custom statistics or visualizations about a watch.

#### Creating a UI Stats Tab Plugin

1. Create a Python file in a directory that will be loaded by the plugin system.

2. Use the `global_hookimpl` decorator to implement the `ui_edit_stats_extras` hook:

```python
import pluggy
from loguru import logger

global_hookimpl = pluggy.HookimplMarker("changedetectionio")

@global_hookimpl
def ui_edit_stats_extras(watch):
    """Add custom content to the stats tab"""
    # Calculate or retrieve your stats
    my_stat = calculate_something(watch)
    
    # Return HTML content as a string
    html = f"""
    <div class="my-plugin-stats">
        <h4>My Plugin Statistics</h4>
        <p>My statistic: {my_stat}</p>
    </div>
    """
    return html
```

3. The HTML you return will be included in the Stats tab.

