export default function Metric({label,value,sub,tone}:{label:string;value:string;sub?:string;tone?:'good'|'bad'|'muted'}){
  return <div className="metric"><span>{label}</span><strong className={tone||''}>{value}</strong>{sub&&<small>{sub}</small>}</div>
}