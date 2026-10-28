import com.android.apksig.ApkVerifier;
import java.io.File;
import java.util.List;

public final class VerifyTool {
    public static void main(String[] args) throws Exception {
        File apk = new File(args[0]);
        ApkVerifier.Result r = new ApkVerifier.Builder(apk).build().verify();
        System.out.println("verified=" + r.isVerified() + " v1=" + r.isVerifiedUsingV1Scheme()
                + " v2=" + r.isVerifiedUsingV2Scheme() + " v3=" + r.isVerifiedUsingV3Scheme());
        List<ApkVerifier.IssueWithParams> errs = r.getErrors();
        for (ApkVerifier.IssueWithParams e : errs) System.out.println("ERR " + e);
    }
}
