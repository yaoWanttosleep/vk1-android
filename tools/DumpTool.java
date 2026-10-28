import com.android.apksig.internal.apk.AndroidBinXmlParser;
import java.io.File;
import java.util.zip.ZipEntry;
import java.util.zip.ZipFile;

public final class DumpTool {
    public static void main(String[] args) throws Exception {
        ZipFile zip = new ZipFile(new File(args[0]));
        ZipEntry e = zip.getEntry("AndroidManifest.xml");
        byte[] bytes = zip.getInputStream(e).readAllBytes();
        AndroidBinXmlParser p = new AndroidBinXmlParser(java.nio.ByteBuffer.wrap(bytes));
        int depth = 0;
        while (p.next() != AndroidBinXmlParser.EVENT_END_DOCUMENT) {
            if (p.getEventType() == AndroidBinXmlParser.EVENT_START_ELEMENT) {
                StringBuilder sb = new StringBuilder();
                for (int i = 0; i < depth; i++) sb.append("  ");
                sb.append('<').append(p.getName());
                for (int i = 0; i < p.getAttributeCount(); i++) {
                    sb.append(' ').append(p.getAttributeNamespace(i)).append(':')
                      .append(p.getAttributeName(i));
                    switch (p.getAttributeValueType(i)) {
                        case AndroidBinXmlParser.VALUE_TYPE_STRING:
                            sb.append("=\"").append(p.getAttributeStringValue(i)).append('"'); break;
                        case AndroidBinXmlParser.VALUE_TYPE_INT:
                            sb.append("=int:").append(p.getAttributeIntValue(i)); break;
                        case AndroidBinXmlParser.VALUE_TYPE_BOOLEAN:
                            sb.append("=bool:").append(p.getAttributeBooleanValue(i)); break;
                        default:
                            sb.append("=type").append(p.getAttributeValueType(i));
                    }

                }
                sb.append('>');
                System.out.println(sb);
                depth++;
            } else if (p.getEventType() == AndroidBinXmlParser.EVENT_END_ELEMENT) {
                depth--;
            }
        }
        zip.close();
    }
}
