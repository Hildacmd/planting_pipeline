source("Methodology_Testing/theme.R")
z<-readRDS("/tmp/gdd_val.rds"); G<-z$G; d<-z$d; cal<-z$cal
STG<-c("adv. vegetative"=0.42,"flowering"=0.55,"grain fill"=0.72)   # fractions of GDD to maturity
SEL<-c("Kitui","Bungoma","Nyandarua")   # hot lowland -> mid -> cool highland
CO<-c(PAL[["two"]],PAL[["held"]],PAL[["e"]])
PD<-8                                    # planting dekad, Mar-d2
TGT<-2250                                # calibrated late-class target
PX("Methodology_Testing/figs/gdd_prognostic.png",2080,940)
layout(matrix(1:2,1,2),widths=c(1.18,.92))
par(mar=c(6.4,6.4,6.6,3.2),oma=c(2.6,0,3.8,.4),xpd=FALSE)

## A - the same thermal target, three different calendars
mx<-36; XMAX<-372
plot(NA,xlim=c(0,XMAX),ylim=c(0,TGT*1.10),axes=FALSE,xlab="",ylab="")
abline(h=pretty(c(0,TGT),5),col=GRID,lwd=1)
for(j in seq_along(STG)) segments(0,TGT*STG[j],XMAX*0.868,TGT*STG[j],col=ACC,lty=3,lwd=1.3)
segments(0,TGT,XMAX*0.855,TGT,col=ACC,lty=2,lwd=1.5)
for(j in seq_along(STG)) text(XMAX*0.868,TGT*STG[j],names(STG)[j],adj=0,cex=.72,col=ACC,font=2)
text(XMAX*0.868,TGT,"maturity",adj=0,cex=.72,col=ACC,font=2)
for(i in seq_along(SEL)){ jj<-which(d$county==SEL[i]); cl<-CO[i]
  cum<-cumsum(sapply(0:(mx-1),function(q) G[jj,((PD-1+q)%%36)+1])); x<-(1:mx)*10.14
  kk<-which(cum>=TGT)[1]; if(is.na(kk)) kk<-mx
  lines(x[1:kk],pmin(cum[1:kk],TGT),col=cl,lwd=3.0)          # stop the curve at maturity
  points(x[kk],TGT,pch=19,col=cl,cex=1.35)
  ml<-which(cum>=TGT*0.80)[1]
  text(x[ml]-6,TGT*0.80,SEL[i],adj=1,cex=.80,col=cl,font=2)
  text(x[kk],TGT+105,sprintf("%.0f d",x[kk]),adj=.5,cex=.76,col=cl,font=2)
  for(j in seq_along(STG)){ th<-TGT*STG[j]; k<-which(cum>=th)[1]
    if(!is.na(k)){ points(x[k],th,pch=19,col=cl,cex=.95)
      text(x[k],th-105,sprintf("%.0f",x[k]),adj=.5,cex=.66,col=cl,font=2)}}}
gridx(seq(0,300,50),cex=.80,line=3.2,title="days after planting")
gridy(pretty(c(0,TGT),5),cex=.80,line=3.8,title="cumulative growing degree days")
ttl("A. One thermal target, three calendars",
    "Planting fixed at Mar-d2. Numbers are the projected day of each stage.",line=3.0,subline=1.8)

## B - lead time: how far ahead each stage is known
par(mar=c(6.0,11.2,6.6,3.4))
ref<-z$ref; ref<-ref[ref$season=="long",]
lt<-do.call(rbind,lapply(seq_len(nrow(ref)),function(i){
  jj<-ref$j[i]; cum<-cumsum(sapply(0:39,function(q) G[jj,((ref$plant_dekad[i]-1+q)%%36)+1]))
  tg<-cal[[as.character(ref$maturity_class[i])]]
  data.frame(cty=ref$cty[i],
    veg=(which(cum>=tg*STG[1])[1])*10.14, flo=(which(cum>=tg*STG[2])[1])*10.14,
    grf=(which(cum>=tg*STG[3])[1])*10.14, mat=(which(cum>=tg)[1])*10.14)}))
lt<-lt[complete.cases(lt),]; lt<-lt[order(lt$flo),]
n<-nrow(lt)
plot(NA,xlim=c(0,max(lt$mat)*1.06),ylim=c(.4,n+.6),axes=FALSE,xlab="",ylab="")
abline(v=seq(0,300,50),col=GRID,lwd=1)
for(r in 1:n){y<-n-r+1
  segments(0,y,lt$mat[r],y,col="#DCD6CA",lwd=4.2,lend=1)
  points(lt$veg[r],y,pch=19,col="#9A9287",cex=.72)
  points(lt$flo[r],y,pch=19,col=PAL[["two"]],cex=.92)
  points(lt$grf[r],y,pch=19,col=PAL[["held"]],cex=.82)}
gridy(n:1,lt$cty,cex=.68)
gridx(seq(0,300,50),cex=.80,line=3.2,title="days of lead time from the planting date")
ttl("B. Dated before it happens",
    sprintf("Kenya long rains, n=%d counties, sorted by flowering date",n),line=3.0,subline=1.8)
mtext(sprintf("flowering lead time: median %.0f d, range %.0f-%.0f d",median(lt$flo),min(lt$flo),max(lt$flo)),
  3,line=0.5,adj=0,cex=.72,col=INK,font=2)
par(fig=c(0,1,0,1),oma=c(0,0,0,0),mar=c(0,0,0,0),new=TRUE,xpd=NA)
plot(0:1,0:1,type="n",axes=FALSE,xlab="",ylab="")
legend("bottom",horiz=TRUE,legend=c("advanced vegetative","flowering","grain filling","to maturity"),
  pch=c(19,19,19,NA),lwd=c(NA,NA,NA,4.2),col=c("#9A9287",PAL[["two"]],PAL[["held"]],"#DCD6CA"),
  bty="n",cex=.84,text.col=INK,pt.cex=c(.80,1.0,.90,NA),inset=c(0,.005))
suptitle("The clock is prognostic: it dates each stage from the planting date and a temperature series",
 c("Thermal time accumulates at a rate set by temperature, so a fixed GDD target lands on a different calendar date in every county - and that date is known at planting.",
   "In the cool highland the same target takes twice as long to reach as in the hot lowland. A fixed calendar cycle cannot represent that; a thermal one does it by construction."))
dev.off(); cat("ok\n")
