package com.example;

import java.io.FileInputStream;
import java.io.IOException;
import java.io.InputStream;

public class FirstBytesReader {
    public byte[] readFirst(String path) throws IOException {
        InputStream in = new FileInputStream(path);
        try {
            byte[] buf = new byte[1024];
            int n = in.read(buf);
            byte[] out = new byte[n];
            System.arraycopy(buf, 0, out, 0, n);
            return out;
        } finally {
            in.close();
        }
    }
}
