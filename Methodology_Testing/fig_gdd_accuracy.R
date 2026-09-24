source("Methodology_Testing/theme.R")
z<-readRDS("/tmp/gdd_val.rds"); ref<-z$ref
ref$fix<-ifelse(ref$season=="long",120,90)
st<-function(p,o) c(mae=mean(abs(p-o),na.rm=TRUE),bias=mean(p-o,na.rm=TRUE),r=cor(p,o,use="complete.obs"))
A<-list(list("fixed configured cycle",ref$fix,"#9A9287"),
        list("GDD clock, shipped targets",ref$pred_ship,PAL[["held"]]),
        list("GDD clock, calibrated targets",ref$pred_cal,PAL[["one"]]))
PX("Methodology_Testing/figs/gdd_accuracy.png",2100,900)
layout(matrix(1:3,1,3),widths=c(1.06,1.06,.98))
par(mar=c(6.2,6.4,6.4,2.6),oma=c(.4,0,3.8,.4),xpd=FALSE)
LIM<-c(60,320)
for(a in A[2:3]){
  plot(NA,xlim=LIM,ylim=LIM,axes=FALSE,xlab="",ylab="")
  abline(h=seq(100,300,50),v=seq(100,300,50),col=GRID,lwd=1)
  segments(LIM[1],LIM[1],LIM[2],LIM[2],col=MUT,lty=3,lwd=1.4)
  points(ref$cycle_days,a[[2]],pch=19,col=paste0(a[[3]],"AA"),cex=1.2)
  s<-st(a[[2]],ref$cycle_days)
  gridx(seq(100,300,50),cex=.80,line=3.2,title="farmer-reported cycle (days)")
  gridy(seq(100,300,50),cex=.80,line=3.6,title="GDD clock projection (days)")
  ttl(sprintf("%s. %s",if(identical(a,A[[2]]))"A" else "B",a[[1]]),
      sprintf("MAE %.0f d   bias %+.0f d   r = %+.2f",s[1],s[2],s[3]),line=3.0,subline=1.8)
  text(LIM[1]+6,LIM[2]-6,"dotted = 1:1",adj=0,cex=.72,col=MUT)}
## C - the comparison that matters
par(mar=c(6.2,14.6,6.4,3.4))
plot(NA,xlim=c(0,.98),ylim=c(.4,3.6),axes=FALSE,xlab="",ylab="")
abline(v=seq(0,.9,.3),col=GRID,lwd=1)
for(i in 1:3){ y<-4-i; s<-st(A[[i]][[2]],ref$cycle_days); cl<-A[[i]][[3]]
  rect(0,y-.24,s[3],y+.24,col=paste0(cl,"38"),border=NA)
  segments(0,y,s[3],y,col=cl,lwd=4,lend=1)
  text(s[3]+.020,y,sprintf("%+.2f",s[3]),adj=0,cex=.84,col=cl,font=2,xpd=NA)}
LB<-sapply(1:3,function(i){s<-st(A[[i]][[2]],ref$cycle_days);sprintf("%s\n(MAE %.0f d)",A[[i]][[1]],s[1])})
gridy(3:1,LB,cex=.80)
gridx(seq(0,.9,.3),cex=.80,line=3.2,title="correlation with farmer-reported cycle length")
ttl("C. Structure, not level","rank agreement with the reported cycle",line=3.0,subline=1.8)
suptitle("The clock reproduces farmer-reported cycle length; a fixed cycle does not",
 c(sprintf("n = %d county-seasons from the Kenya Insurance Atlas (%d long rains, %d short rains).",nrow(ref),sum(ref$season=="long"),sum(ref$season=="short")),
   "The clock ranks cycle length at r = +0.79 whichever GDD target is used; the fixed configured cycle manages r = +0.22.",
   "The absolute level depends on the target: the shipped values run 36 days short, recalibrated they sit within 10 days."))
dev.off(); cat("ok\n")
