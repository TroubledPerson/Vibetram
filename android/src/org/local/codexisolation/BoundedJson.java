package org.local.codexisolation;
import java.nio.ByteBuffer;
import java.nio.charset.*;
import java.util.*;

/** Strict bounded fixture parser; no I/O, reflection, or application state. */
final class BoundedJson {
    private final String text; private int pos,nodes;
    private BoundedJson(byte[] bytes) {
        if(bytes.length>65536)throw bad();
        try{text=StandardCharsets.UTF_8.newDecoder().onMalformedInput(CodingErrorAction.REPORT).onUnmappableCharacter(CodingErrorAction.REPORT).decode(ByteBuffer.wrap(bytes)).toString();}
        catch(CharacterCodingException e){throw bad();}
    }
    static Object parse(byte[] bytes){BoundedJson p=new BoundedJson(bytes);Object v=p.value(0);p.space();if(p.pos!=p.text.length())throw bad();return v;}
    private static SecurityException bad(){return new SecurityException("Malformed bounded model JSON");}
    private void space(){while(pos<text.length()&&" \r\n\t".indexOf(text.charAt(pos))>=0)pos++;}
    private boolean eat(char c){space();if(pos<text.length()&&text.charAt(pos)==c){pos++;return true;}return false;}
    private Object value(int depth){space();if(depth>16||++nodes>4096||pos>=text.length())throw bad();char c=text.charAt(pos);
        if(c=='"')return string();
        if(c=='{'){pos++;Map<String,Object> m=new LinkedHashMap<>();if(eat('}'))return m;do{space();if(pos>=text.length()||text.charAt(pos)!='"')throw bad();String k=string();if(m.containsKey(k)||!eat(':'))throw bad();m.put(k,value(depth+1));}while(eat(','));if(!eat('}'))throw bad();return m;}
        if(c=='['){pos++;List<Object> a=new ArrayList<>();if(eat(']'))return a;do{a.add(value(depth+1));}while(eat(','));if(!eat(']'))throw bad();return a;}
        for(String word:new String[]{"true","false","null"})if(text.startsWith(word,pos)){pos+=word.length();return word.equals("null")?null:Boolean.valueOf(word);}
        int start=pos;while(pos<text.length()&&"-+0123456789.eE".indexOf(text.charAt(pos))>=0){if(pos-start>=64)throw bad();pos++;}
        String num=text.substring(start,pos);if(!num.matches("-?(0|[1-9][0-9]*)(\\.[0-9]+)?([eE][+-]?[0-9]+)?"))throw bad();
        try{return new java.math.BigDecimal(num);}catch(NumberFormatException e){throw bad();}
    }
    private String string(){pos++;StringBuilder b=new StringBuilder();boolean end=false;
        while(pos<text.length()){char c=text.charAt(pos++);if(c=='"'){end=true;break;}if(c<32)throw bad();
            if(c=='\\'){if(pos>=text.length())throw bad();char e=text.charAt(pos++);switch(e){case '"':case '\\':case '/':c=e;break;case 'b':c='\b';break;case 'f':c='\f';break;case 'n':c='\n';break;case 'r':c='\r';break;case 't':c='\t';break;case 'u':if(pos+4>text.length())throw bad();int n=0;for(int i=0;i<4;i++){char hchar=text.charAt(pos++);if(!((hchar>='0'&&hchar<='9')||(hchar>='a'&&hchar<='f')||(hchar>='A'&&hchar<='F')))throw bad();int h=Character.digit(hchar,16);n=n*16+h;}c=(char)n;break;default:throw bad();}}
            b.append(c);
        }
        if(!end)throw bad();for(int i=0;i<b.length();i++){char c=b.charAt(i);if(Character.isHighSurrogate(c)){if(++i>=b.length()||!Character.isLowSurrogate(b.charAt(i)))throw bad();}else if(Character.isLowSurrogate(c))throw bad();}return b.toString();
    }
}
