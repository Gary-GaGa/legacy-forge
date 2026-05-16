package com.example;

import java.text.SimpleDateFormat;
import java.util.Date;

public class Timestamper {
    public String now() {
        Date d = new Date();
        SimpleDateFormat fmt = new SimpleDateFormat("yyyy-MM-dd HH:mm:ss");
        return fmt.format(d);
    }
}
