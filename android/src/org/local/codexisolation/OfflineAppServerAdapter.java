package org.local.codexisolation;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.math.BigDecimal;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.Arrays;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.TimeoutException;
import java.util.concurrent.atomic.AtomicBoolean;

/** Parent UID only. Runs one credential-free initialize exchange; never sends output over Binder. */
final class OfflineAppServerAdapter {
    static final int MAX_LINE = 16 * 1024, MAX_STDERR = 64 * 1024;
    enum Mode { INITIALIZE, CANCEL_AFTER_REQUEST, PROCESS_DEATH_AFTER_REQUEST }
    private static final byte[] INITIALIZE = ("{\"id\":1,\"method\":\"initialize\",\"params\":{\"clientInfo\":{\"name\":\"android-offline-adapter\",\"title\":null,\"version\":\"0.1\"}}}\n")
            .getBytes(StandardCharsets.UTF_8);
    private static final byte[] INITIALIZED = "{\"method\":\"initialized\"}\n".getBytes(StandardCharsets.UTF_8);
    interface ProcessFactory { Process start(List<String> command, Map<String,String> env) throws IOException; }
    static final ProcessFactory SYSTEM = (command, env) -> {
        ProcessBuilder b = new ProcessBuilder(command);
        b.environment().clear(); b.environment().putAll(env);
        return b.start();
    };
    static final class Result {
        final String home; final int stderrBytes; final Mode mode;
        Result(String home, int stderrBytes, Mode mode) {
            this.home=home; this.stderrBytes=stderrBytes; this.mode=mode;
        }
    }
    private final ProcessFactory factory;
    private final AtomicBoolean started = new AtomicBoolean(), cancelled = new AtomicBoolean();
    private volatile Process child;
    private volatile String stage="NOT_STARTED";
    OfflineAppServerAdapter(ProcessFactory factory) { this.factory=factory; }
    String stage() { return stage; }

    void cancel() {
        cancelled.set(true);
        Process p=child; if(p!=null) p.destroyForcibly();
    }

    Result run(File filesDir, File binary) throws Exception {
        return run(filesDir,binary,Mode.INITIALIZE);
    }

    Result run(File filesDir, File binary, Mode mode) throws Exception {
        if(!started.compareAndSet(false,true)) throw new IllegalStateException("ALREADY_RUN");
        if(cancelled.get()) throw new IllegalStateException("CANCELLED");
        stage="HOME_CHECK";
        File privateDir=filesDir.getCanonicalFile();
        if(!privateDir.isDirectory()) throw new IllegalStateException("PRIVATE_FILES_MISSING");
        File rawHome=new File(privateDir,"offline-appserver-home");
        Files.createDirectories(rawHome.toPath());
        File home=rawHome.getCanonicalFile();
        if(!privateDir.equals(home.getParentFile()) || !home.isDirectory())
            throw new SecurityException("HOME_OUTSIDE_PRIVATE_FILES");
        if(!binary.isFile() || !binary.canExecute()) throw new IllegalStateException("NATIVE_BINARY_UNAVAILABLE");
        String expectedHome=home.getPath();
        Map<String,String> env=new HashMap<>();
        env.put("PATH","/system/bin"); env.put("HOME",expectedHome); env.put("CODEX_HOME",expectedHome);
        ExecutorService readers=Executors.newFixedThreadPool(2);
        Process p=null;
        try {
            stage="PROCESS_START";
            p=factory.start(Arrays.asList(binary.getAbsolutePath(),"--listen","stdio://",
                    "--disable-plugin-startup-tasks-for-tests"),env);
            child=p;
            if(cancelled.get()) throw new IllegalStateException("CANCELLED");
            final Process running=p;
            Future<Map<?,?>> response=readers.submit(() -> readInitialize(running.getInputStream()));
            Future<Integer> stderr=readers.submit(() -> drainStderr(running.getErrorStream()));
            Future<Integer> tail=null;
            OutputStream in=p.getOutputStream();
            try {
                stage="REQUEST_WRITE";
                in.write(INITIALIZE); in.flush();
                if(mode!=Mode.INITIALIZE){
                    // A real bounded request is in flight. The two manual
                    // lifecycle cases then terminate this child deliberately.
                    stage="CONTROL_KILL";
                    if(!p.isAlive()) throw new IllegalStateException("EARLY_PROCESS_EXIT");
                    if(mode==Mode.CANCEL_AFTER_REQUEST) cancel();
                    else p.destroyForcibly();
                    stage="KILL_WAIT";
                    if(!p.waitFor(3,TimeUnit.SECONDS) || p.isAlive())
                        throw new IllegalStateException("KILL_TIMEOUT");
                    if(p.exitValue()==0) throw new IllegalStateException("UNEXPECTED_CLEAN_EXIT");
                    stage="KILL_STDERR";
                    int stderrBytes;
                    try { stderrBytes=stderr.get(2,TimeUnit.SECONDS); }
                    catch(ExecutionException e){
                        // Android may close a process pipe while the child is
                        // forcibly destroyed. The child exit has already been
                        // verified; preserve this diagnostic distinctly.
                        if(e.getCause() instanceof IOException) stderrBytes=-1;
                        else throw e;
                    }
                    catch(TimeoutException e){throw new IllegalStateException("STDERR_DRAIN_TIMEOUT",e);}
                    stage="COMPLETE";
                    return new Result(expectedHome,stderrBytes,mode);
                }
                stage="RESPONSE_WAIT";
                Map<?,?> frame=response.get(15,TimeUnit.SECONDS);
                checkResponse(frame,expectedHome);
                if(cancelled.get()) throw new IllegalStateException("CANCELLED");
                // Keep consuming bounded post-initialize notifications so the child
                // cannot stall on a full stdout pipe before its normal EOF exit.
                Future<Integer> stdoutTail=readers.submit(() -> drain(running.getInputStream(),MAX_STDERR,"STDOUT_TAIL_OVERSIZE"));
                stage="ACK_WRITE";
                in.write(INITIALIZED); in.flush();
                // The future remains active while stdin closes and the child exits.
                tail=stdoutTail;
            } finally {
                try { in.close(); }
                catch(IOException e){
                    // A forced kill can close stdin before Java closes its
                    // OutputStream. Do not turn verified child death into an
                    // unrelated stream-close failure.
                    if(mode==Mode.INITIALIZE || p.isAlive())
                        throw new IllegalStateException("STDIN_CLOSE_ERROR",e);
                }
            }
            stage="EXIT_WAIT";
            if(!p.waitFor(5,TimeUnit.SECONDS)) throw new IllegalStateException("EXIT_TIMEOUT");
            tail.get(2,TimeUnit.SECONDS);
            int stderrBytes=stderr.get(2,TimeUnit.SECONDS);
            if(cancelled.get()) throw new IllegalStateException("CANCELLED");
            if(p.exitValue()!=0) throw new IllegalStateException("NONZERO_EXIT");
            stage="COMPLETE";
            return new Result(expectedHome,stderrBytes,Mode.INITIALIZE);
        } finally {
            if(p!=null && p.isAlive()) {p.destroyForcibly();p.waitFor(2,TimeUnit.SECONDS);}
            child=null;
            readers.shutdownNow();
        }
    }

    private static Map<?,?> readInitialize(InputStream out) throws Exception {
        for(int i=0;i<8;i++) {
            byte[] frame=readLine(out);
            Object parsed=BoundedJson.parse(frame);
            if(!(parsed instanceof Map)) throw new SecurityException("NON_OBJECT_FRAME");
            Map<?,?> map=(Map<?,?>)parsed;
            if(BigDecimal.ONE.equals(map.get("id"))) return map;
        }
        throw new IllegalStateException("NO_MATCHING_RESPONSE");
    }
    private static byte[] readLine(InputStream in) throws IOException {
        ByteArrayOutputStream line=new ByteArrayOutputStream();
        while(true) {
            int b=in.read();
            if(b<0) throw new IllegalStateException("EARLY_STDOUT_EOF");
            if(b=='\n') return line.toByteArray();
            if(line.size()>=MAX_LINE) throw new SecurityException("STDOUT_FRAME_OVERSIZE");
            line.write(b);
        }
    }
    private static int drainStderr(InputStream in) throws IOException {
        return drain(in,MAX_STDERR,"STDERR_OVERSIZE");
    }
    private static int drain(InputStream in,int limit,String failure) throws IOException {
        int total=0; byte[] buffer=new byte[1024]; int n;
        while((n=in.read(buffer))!=-1) {
            if(n>limit-total) throw new SecurityException(failure);
            total+=n;
        }
        return total;
    }
    private static void checkResponse(Map<?,?> frame,String expectedHome) {
        if(frame.containsKey("error") || !BigDecimal.ONE.equals(frame.get("id")))
            throw new SecurityException("INITIALIZE_RPC_ERROR");
        Object payload=frame.get("result");
        if(!(payload instanceof Map)) throw new SecurityException("INITIALIZE_RESULT_MISSING");
        Map<?,?> result=(Map<?,?>)payload;
        if(!(result.get("userAgent") instanceof String) || ((String)result.get("userAgent")).isEmpty()
                || !(result.get("platformFamily") instanceof String) || ((String)result.get("platformFamily")).isEmpty()
                || !"android".equals(result.get("platformOs")))
            throw new SecurityException("INITIALIZE_PLATFORM_INVALID");
        if(!expectedHome.equals(result.get("codexHome")))
            throw new SecurityException("INITIALIZE_HOME_MISMATCH");
    }
}
