package com.lyonbegin.aiinvestmts;

import android.app.Activity;
import android.os.Bundle;
import android.content.Context;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.view.Gravity;
import android.view.View;
import android.view.inputmethod.InputMethodManager;
import android.widget.*;
import java.util.*;

/** Independent Android MTS prototype. No vendor code, data, branding or live trading. */
public final class MainActivity extends Activity implements AppState.Navigation {
  private static final int BG=0xFFF7F9FC, INK=0xFF202B39, SUB=0xFF6C7889, BLUE=0xFF266BDE, WHITE=Color.WHITE;
  private final AppState state=new AppState();
  private SharedPreferences prefs;
  private LinearLayout root, body, footer;
  private final String[] agents={"반도체 분석 AI","미국주식 분석 AI","배당·ETF AI","시장 뉴스 AI"};
  private final String[] descriptions={"실적·공시·메모리 시장","지수·글로벌 기업","장기 투자·배당 정보","시장 이벤트·경제 뉴스"};

  @Override public void onCreate(Bundle saved){super.onCreate(saved);prefs=getSharedPreferences("ai_invest_studio",MODE_PRIVATE);getWindow().setStatusBarColor(WHITE);getWindow().setNavigationBarColor(0xFF131D2E);getWindow().getDecorView().setSystemUiVisibility(View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR);render();}
  private int d(int px){return Math.round(px*getResources().getDisplayMetrics().density);}
  private GradientDrawable bg(int color,int r){GradientDrawable g=new GradientDrawable();g.setColor(color);g.setCornerRadius(d(r));return g;}
  private TextView t(String str,int size,int col,boolean bold){TextView v=new TextView(this);v.setText(str);v.setTextSize(size);v.setTextColor(col);v.setGravity(Gravity.CENTER_VERTICAL);if(bold)v.setTypeface(Typeface.DEFAULT,Typeface.BOLD);return v;}
  private LinearLayout col(){LinearLayout v=new LinearLayout(this);v.setOrientation(1);return v;}
  private LinearLayout row(){LinearLayout v=new LinearLayout(this);v.setOrientation(0);v.setGravity(Gravity.CENTER_VERTICAL);return v;}
  private void add(LinearLayout parent,View child){parent.addView(child,new LinearLayout.LayoutParams(-1,-2));}
  private void gap(LinearLayout parent,int dp){View v=new View(this);parent.addView(v,new LinearLayout.LayoutParams(1,d(dp)));}
  private void headline(String name,String note){add(body,t(name,26,INK,true));gap(body,5);add(body,t(note,13,SUB,false));gap(body,19);}
  private void section(String name){gap(body,7);add(body,t(name,15,INK,true));gap(body,11);}
  private void tile(String title,String desc,Runnable click){LinearLayout wrap=row();wrap.setBackground(bg(WHITE,15));wrap.setPadding(d(15),d(16),d(13),d(16));LinearLayout words=col();add(words,t(title,16,INK,true));if(desc!=null){gap(words,5);add(words,t(desc,12,SUB,false));}wrap.addView(words,new LinearLayout.LayoutParams(0,-2,1));if(click!=null){wrap.addView(t("›",28,SUB,false));wrap.setOnClickListener(v->click.run());}add(body,wrap);gap(body,9);}
  private void button(String title,boolean primary,Runnable click){TextView b=t(title,15,primary?WHITE:BLUE,true);b.setGravity(Gravity.CENTER);b.setPadding(d(12),d(14),d(12),d(14));b.setBackground(bg(primary?BLUE:0xFFE5EDFC,11));add(body,b);gap(body,11);b.setOnClickListener(v->click.run());}
  private EditText field(String label,String value,boolean number){add(body,t(label,13,SUB,true));gap(body,6);EditText x=new EditText(this);x.setText(value);x.setTextSize(16);x.setSingleLine(true);x.setPadding(d(14),d(12),d(14),d(12));x.setBackground(bg(WHITE,10));if(number)x.setInputType(android.text.InputType.TYPE_CLASS_NUMBER);add(body,x);gap(body,13);return x;}
  private void render(){root=col();root.setBackgroundColor(BG);setContentView(root);LinearLayout header=row();header.setPadding(d(19),d(16),d(19),d(15));header.setBackgroundColor(WHITE);TextView title=t("AI 투자 스튜디오",19,INK,true);header.addView(title,new LinearLayout.LayoutParams(0,-2,1));header.addView(t("프로토타입",12,SUB,false));add(root,header);
    ScrollView sc=new ScrollView(this);sc.setFillViewport(false);root.addView(sc,new LinearLayout.LayoutParams(-1,0,1));body=col();body.setPadding(d(17),d(19),d(17),d(15));sc.addView(body);
    switch(state.page){case "discover":discover();break;case "stock":stock();break;case "watch":watch();break;case "agents":agents();break;case "chat":chat();break;case "ticket":ticket();break;case "confirm":confirm();break;case "assets":assets();break;default:home();}
    footer=row();footer.setBackgroundColor(WHITE);footer.setPadding(d(4),d(9),d(4),d(9));tab("홈","home");tab("발견","discover");tab("AI 상담","agents");tab("관심","watch");tab("내 자산","assets");add(root,footer);
  }
  private void tab(String label,String dest){TextView v=t(label,12,state.page.equals(dest)?BLUE:SUB,state.page.equals(dest));v.setGravity(Gravity.CENTER);footer.addView(v,new LinearLayout.LayoutParams(0,d(40),1));v.setOnClickListener(w->open(dest));}
  @Override public void open(String target){state.page=target;render();}
  @Override public void stock(String symbol){state.symbol=symbol;open("stock");}
  @Override public void chat(String agent,String prev){state.agent=agent;state.previousPage=prev;state.messages.clear();open("chat");}
  private Set<String> watchSet(){return new HashSet<>(prefs.getStringSet("watchlist",Collections.emptySet()));}
  private boolean tracked(String symbol){return watchSet().contains(symbol);}
  private void toggleWatch(){Set<String> list=watchSet();if(!list.add(state.symbol))list.remove(state.symbol);prefs.edit().putStringSet("watchlist",list).apply();render();}
  private void home(){headline("오늘의 투자","종목 탐색부터 전문 AI 상담까지");tile("내 투자 현황","공식 증권계좌 연결 전 · 잔고 미표시",()->open("assets"));section("많이 찾는 종목");tile("삼성전자","실시간 시세 미연동",()->stock("삼성전자"));tile("S&P 500 ETF","실시간 시세 미연동",()->stock("S&P 500 ETF"));section("AI 투자 상담");tile("반도체 분석 AI","실적과 공시 중심 상담",()->chat(agents[0],"home"));tile("미국주식 분석 AI","글로벌 기업 관련 질문",()->chat(agents[1],"home"));button("모든 전문 AI 보기",true,()->open("agents"));}
  private void discover(){headline("발견","검색한 종목을 선택하면 상세화면이 열립니다");EditText query=field("종목명 또는 상품명", "",false);button("종목 검색",true,()->{String q=query.getText().toString().trim();if(q.isEmpty())Toast.makeText(this,"종목을 입력해 주세요",Toast.LENGTH_SHORT).show();else stock(q);});section("빠른 탐색");tile("삼성전자","국내주식 · 종목 상세",()->stock("삼성전자"));tile("S&P 500 ETF","미국시장 · 지수 ETF",()->stock("S&P 500 ETF"));tile("AI에게 시장 질문하기","투자 전문가 선택",()->open("agents"));}
  private void stock(){headline(state.symbol,"종목 상세 · 실시간 가격 API 연결 전");tile("현재가 / 등락률","공식 시세 공급자 미연결",null);tile("차트 / 실적 / 뉴스","연결된 데이터 없음",null);button(tracked(state.symbol)?"관심종목 해제":"관심종목 등록",false,this::toggleWatch);button("이 종목을 AI에게 질문",true,()->chat("반도체 분석 AI","stock"));button("매수·매도 주문안 작성",false,()->{state.draft.symbol=state.symbol;open("ticket");});}
  private void watch(){headline("관심종목","기기에만 저장됩니다");Set<String> watched=watchSet();if(watched.isEmpty())tile("관심종목이 없습니다","종목 상세에서 등록해 주세요",()->open("discover"));else {List<String> a=new ArrayList<>(watched);Collections.sort(a);for(String s:a)tile(s,"종목 상세로 이동",()->stock(s));}button("종목 찾기",true,()->open("discover"));}
  private void agents(){headline("전문 AI 선택","분야별 상담 화면 · 실제 AI 서버 미연결");for(int i=0;i<agents.length;i++){final String a=agents[i];tile(a,descriptions[i],()->chat(a,"agents"));}}
  private void chat(){headline(state.agent,"상담 내용은 이 화면의 임시 기록입니다");tile("질문 예시","실적을 어떻게 해석하나요?",null);for(String m:state.messages){TextView bubble=t(m,15,INK,false);bubble.setPadding(d(13),d(12),d(13),d(12));bubble.setBackground(bg(WHITE,12));add(body,bubble);gap(body,8);}EditText query=field("질문 입력","",false);button("질문 기록",true,()->{String q=query.getText().toString().trim();if(q.isEmpty())return;state.messages.add("나: "+q);state.messages.add("AI: 현재 서버 미연동 · 답변 생성 안 됨");render();});button("주문안 작성",false,()->{state.draft.symbol=state.symbol;open("ticket");});button("이전 화면",false,()->open(state.previousPage));}
  private void assets(){headline("내 자산","증권계좌가 연결되지 않았습니다");tile("연결된 계좌 0개","계좌정보를 요청하지 않습니다",null);tile("보유종목 / 예수금","공식 API 연동 후 사용 가능",null);tile("주문 내역","실거래 미지원",null);button("관심종목 보기",true,()->open("watch"));}
  private void ticket(){headline("주문안 작성","실제 증권사 주문은 전송되지 않습니다");EditText sym=field("종목",state.draft.symbol,false);Spinner sides=new Spinner(this);ArrayAdapter<String> adapter=new ArrayAdapter<>(this,android.R.layout.simple_spinner_dropdown_item,new String[]{"매수","매도"});sides.setAdapter(adapter);sides.setSelection(state.draft.side.equals("매도")?1:0);add(body,sides);gap(body,12);EditText qty=field("수량 (주)",state.draft.quantity==0?"":String.valueOf(state.draft.quantity),true);EditText price=field("희망 가격 (원)",state.draft.limitPrice==0?"":String.valueOf(state.draft.limitPrice),true);button("주문안 확인",true,()->{try{state.draft.symbol=sym.getText().toString().trim();state.draft.side=String.valueOf(sides.getSelectedItem());state.draft.quantity=Long.parseLong(qty.getText().toString().trim());state.draft.limitPrice=Long.parseLong(price.getText().toString().trim());if(!state.draft.validate())throw new IllegalArgumentException();open("confirm");}catch(Exception e){Toast.makeText(this,"종목·수량·가격을 확인하세요",Toast.LENGTH_SHORT).show();}});}
  private void confirm(){headline("주문안 확인","입력값 검토 전용 · 주문 미전송");tile("종목",state.draft.symbol,null);tile("방향",state.draft.side,null);tile("수량",state.draft.quantity+"주",null);tile("희망 가격",state.draft.limitPrice+"원",null);button("확인 완료 (주문 미실행)",true,()->{Toast.makeText(this,"주문 전송 없이 종료",Toast.LENGTH_SHORT).show();open("home");});button("수정",false,()->open("ticket"));}
  @Override public void onBackPressed(){switch(state.page){case "stock":open("discover");break;case "chat":open(state.previousPage);break;case "confirm":open("ticket");break;default:open("home");}}
}
