package com.example;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

public class CollectionsFactory {
    public List<String> names() {
        List<String> xs = new ArrayList<String>();
        xs.add("a");
        xs.add("b");
        return xs;
    }

    public Map<String, Integer> counts() {
        return new HashMap<String, Integer>();
    }
}
