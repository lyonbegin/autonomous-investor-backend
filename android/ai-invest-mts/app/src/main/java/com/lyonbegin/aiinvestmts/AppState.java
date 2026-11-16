package com.lyonbegin.aiinvestmts;
import java.util.ArrayList;
import java.util.List;

/** Explicit inputs/outputs derived from verified screen navigation and state boundaries. */
public final class AppState {
  public String page="home", symbol="삼성전자", agent="반도체 분석 AI", previousPage="stock";
  public final List<String> messages=new ArrayList<>();
  public final OrderDraft draft=new OrderDraft();
  public static final class OrderDraft {
    public String symbol="삼성전자", side="매수";
    public long quantity=0, limitPrice=0;
    public boolean validate(){return symbol!=null&&!symbol.trim().isEmpty()&&quantity>0&&limitPrice>0;}
    public String summary(){return symbol+" · "+side+" · "+quantity+"주 · "+limitPrice+"원";}
  }
  public interface Navigation {
    void open(String page);
    void stock(String symbol);
    void chat(String agent, String previousPage);
  }
}
