package com.example;

import java.io.IOException;

public class ExceptionHandler {
    public void handle(int kind) {
        try {
            doWork(kind);
        } catch (IOException e) {
            log(e);
        } catch (RuntimeException e) {
            log(e);
        }
    }

    private void doWork(int kind) throws IOException {
        if (kind == 0) {
            throw new IOException("io");
        }
        throw new RuntimeException("rt");
    }

    private void log(Exception e) {
        System.err.println(e.getMessage());
    }
}
