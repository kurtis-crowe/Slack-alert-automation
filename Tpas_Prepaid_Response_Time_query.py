
operation = {}

Tpas_Prt_Query = f"""index=tpas source!="*flix*" source="*pel-tpas*production-duck-cde*.stdout" kubernetes_container_name=*v5* kubernetes_container_name!=v2-account  "Rest client request response" requestResponse.service=*Api requestResponse.operation={operation}

| rename requestResponse.duration as duration
| rename requestResponse.service as Service, requestResponse.operation as Operation
| eval cduration=duration*.625
| eval dduration=duration*.5
| eval duration=if(like(Operation,"%customerCreditCheck%"),cduration,duration)
| eval duration=if(like(Operation,"%shipmentLabel%"),cduration,duration)
| eval duration=if(like(Operation,"%accountDetails%"),cduration,duration)
| eval duration=if(like(Operation,"%createOrder%"),dduration,duration)
| eval duration=if(like(Operation,"%updateOrder%"),dduration,duration)
| eval duration=if(like(Operation,"%finalizeOrder%"),dduration,duration)
| eval duration=if(like(Operation,"%returnOrder%"),dduration,duration)
| eval duration=if(like(Operation,"%submitOrder%"),dduration,duration)
|  eval highres=case((duration>=5000),1,(duration<5000),0)
| stats  count, avg(duration) as mean_avg, median(duration) as median_avg, min(duration) as minimum, max(duration) as maximum sum(highres) as highres by Operation Service
| eval  mean_avg=round(mean_avg), median_avg=round(median_avg), minimum=round(minimum), maximum=round(maximum) 
| rename  mean_avg as MeanAvg , median_avg as MedianAvg, minimum as Min, maximum as Max

| sort  Operation
| eval ManagerClass="T-Mobile Partner API Service" 
| eval AlertName="TPAS: PREPAID API Response Time Failure" 
| eval displayName = "T-Mobile Partner API Service" 
| eval DisplayName = Service.":".Operation 
| eval severityOVO = case((MeanAvg > 7000 and MeanAvg <= 10000), "MAJOR", (MeanAvg > 10000), "CRITICAL" , (MeanAvg < 7000), "MINOR") 

| eval description = "Alertname: ".AlertName." 
| ServiceName: ".Service." 
| OperationName: ".Operation."
| Average Response Time(ms): ".MeanAvg." | Maximum Response Time(ms): ".Max
| table Operation, description, severityOVO
| replace "*,*" with "*/*" """


