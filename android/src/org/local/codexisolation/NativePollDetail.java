package org.local.codexisolation;

/** Accepts only fixed native poll markers and fixed typed I/O categories. */
final class NativePollDetail {
    private NativePollDetail(){}
    private static final String[] NATIVE={
            "CORETEST_POLL_CONNECT_FIRST_SEND_NO_REDIRECT",
            "CORETEST_POLL_CONNECT_FIRST_SEND_AFTER_REDIRECT",
            "CORETEST_POLL_CONNECT_AFTER_PENDING_NO_REDIRECT",
            "CORETEST_POLL_CONNECT_AFTER_PENDING_AFTER_REDIRECT"
    };
    private static final String[] DISPLAY={
            "POLL_CONNECT_FIRST_SEND_NO_REDIRECT",
            "POLL_CONNECT_FIRST_SEND_AFTER_REDIRECT",
            "POLL_CONNECT_AFTER_PENDING_NO_REDIRECT",
            "POLL_CONNECT_AFTER_PENDING_AFTER_REDIRECT"
    };
    static String classify(String raw){
        if(raw==null)return null;
        for(int i=0;i<NATIVE.length;i++){
            if(raw.equals(NATIVE[i]))return DISPLAY[i];
            if(raw.startsWith(NATIVE[i]+"|")){
                String detail=raw.substring(NATIVE[i].length()+1);
                if("IO_REFUSED".equals(detail)||"IO_UNREACHABLE".equals(detail)
                        ||"IO_TIMEOUT".equals(detail)||"IO_NOT_FOUND".equals(detail)
                        ||"IO_RESET".equals(detail)||"IO_ADDR_UNAVAILABLE".equals(detail)
                        ||"IO_NOT_CONNECTED".equals(detail)||"IO_PERMISSION".equals(detail)
                        ||"IO_UNEXPECTED_EOF".equals(detail)||"IO_OTHER".equals(detail)
                        ||"NO_IO_CAUSE".equals(detail))return DISPLAY[i]+"_"+detail;
                return null;
            }
        }
        return null;
    }
}
