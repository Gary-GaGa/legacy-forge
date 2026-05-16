package com.example;

import java.util.concurrent.Executor;

public class TaskRunner {
    public void runLater(Executor exec, final String name) {
        exec.execute(new Runnable() {
            @Override
            public void run() {
                System.out.println("hello " + name);
            }
        });
    }
}
