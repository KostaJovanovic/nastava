package com.valjdakosta.nastava;

import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

public class AppUpdateTest {

    @Test
    public void newer() {
        assertTrue(AppUpdate.newer("0.730", "0.723"));
        assertTrue(AppUpdate.newer("0.1000", "0.999"));
        assertFalse(AppUpdate.newer("0.723", "0.723"));
        assertFalse(AppUpdate.newer("0.722", "0.723"));
        assertFalse(AppUpdate.newer("", "0.723")); // an asset with no label: never an update
        assertTrue(AppUpdate.newer("0.2", "dev"));
    }
}
