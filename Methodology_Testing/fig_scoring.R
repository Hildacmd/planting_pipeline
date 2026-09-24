source("Methodology_Testing/theme.R")
CA<-"#9A9287"; CB<-PAL[["e"]]; CR<-PAL[["two"]]; CG<-PAL[["one"]]

## ================= FIGURE 1: the ceiling trap =================
PX("Methodology_Testing/figs/scoring_ceiling_trap.png",2140,1320)
layout(matrix(1:4,2,2,byrow=TRUE))
par(oma=c(.8,0,7.6,.6),xpd=FALSE)

## A - soil bucket, ward: the verdict flips
par(mar=c(6.2,12.0,6.8,4.0))
S<-data.frame(sc=c("each arm gets\nits own ceiling","ceiling as shipped\n(shared)"),
  d=c(0.0075,-0.097), lo=c(0.0015,-0.132), hi=c(0.0128,-0.063), stringsAsFactors=FALSE)
xr<-c(-.16,.055); tk<-c(-.15,-.10,-.05,0,.05)
plot(NA,xlim=xr,ylim=c(.5,2.5),axes=FALSE,xlab="",ylab="")
abline(v=tk,col=GRID,lwd=1); abline(v=0,col=INK,lwd=1.6)
for(i in 1:2){y<-3-i; cl<-if(S$d[i]>0) CB else CA
  segments(S$lo[i],y,S$hi[i],y,col=cl,lwd=3.2)
  segments(c(S$lo[i],S$hi[i]),y-.11,c(S$lo[i],S$hi[i]),y+.11,col=cl,lwd=2.4)
  points(S$d[i],y,pch=19,col=cl,cex=1.4)
  text(S$d[i],y-.30,if(S$d[i]>0) "SoilGrids wins" else "uniform wins",cex=.84,col=cl,font=2,adj=.5)}
gridy(2:1,S$sc,cex=.88)
gridx(tk,c("-0.15","-0.10","-0.05","0","0.05"),cex=.82,line=3.0,
      title="delta LOO-MAE, uniform minus SoilGrids (t/ha)")
ttl("A. The soil bucket: the verdict reverses","Kenya short rains, ward crop cuts, n = 77",line=3.4,subline=2.0)
text(-.157,2.42,"uniform better",adj=0,cex=.76,col=CA,font=2)
text(.052,2.42,"SoilGrids better",adj=1,cex=.76,col=CB,font=2)

## B - vegetation term: the gain evaporates
par(mar=c(6.2,12.0,6.8,5.0))
V<-data.frame(dom=c("KE long rains","KE short rains","ET Meher"),
  own_V=c(0.625,0.458,0.673), own_D=c(0.611,0.447,0.598),
  shr_V=c(0.659,0.516,1.586), shr_D=c(0.689,0.545,1.268), stringsAsFactors=FALSE)
plot(NA,xlim=c(0,1.72),ylim=c(.5,6.5),axes=FALSE,xlab="",ylab="")
abline(v=seq(0,1.5,.5),col=GRID,lwd=1)
lab<-c(); yy<-6
for(i in 1:3) for(sc in c("own","shr")){
    v<-V[[paste0(sc,"_V")]][i]; d<-V[[paste0(sc,"_D")]][i]
    segments(v,yy,d,yy,col=RULE,lwd=2.4)
    points(v,yy,pch=19,col=CG,cex=1.25); points(d,yy,pch=19,col=CR,cex=1.25)
    text(1.75,yy,if(d<v)"DMP" else "NDVI",adj=0,cex=.74,col=if(d<v)CR else CG,font=2,xpd=NA)
    lab<-c(lab,sprintf("%s, %s",V$dom[i],if(sc=="own")"own ceilings" else "shared")); yy<-yy-1}
gridy(6:1,lab,cex=.76)
gridx(seq(0,1.5,.5),cex=.82,line=3.0,title="leave-one-out MAE (t/ha)   lower is better")
ttl("B. The vegetation term: a gain that was not there",
    "green = NDVI/VCI (shipped)   red = DMP anomaly",line=3.4,subline=2.0)

## C - why: a level shift is absorbed exactly, shown in PREDICTION space
par(mar=c(6.2,7.0,6.8,3.0))
set.seed(3); n<-40
idx<-runif(n,.25,.85); obs<-2.1*idx+rnorm(n,0,.28); idxB<-idx*1.35
ymA<-sum(idx*obs)/sum(idx^2); ymB<-sum(idxB*obs)/sum(idxB^2)
pA<-ymA*idx; pB<-ymB*idxB
plot(NA,xlim=c(0,2.3),ylim=c(0,3.5),axes=FALSE,xlab="",ylab="")
abline(h=pretty(c(0,2.6),5),v=pretty(c(0,2.2),5),col=GRID,lwd=1)
segments(0,0,2.3,2.3,col=MUT,lty=3,lwd=1.4)
points(pA,obs,pch=19,col=CG,cex=1.5); points(pB,obs,pch=21,col=CR,bg=NA,lwd=2.0,cex=1.5)
gridx(pretty(c(0,2.2),5),cex=.82,line=3.0,title="predicted yield (t/ha)")
gridy(pretty(c(0,2.6),5),cex=.82,line=3.4,title="observed yield (t/ha)")
ttl("C. Why a per-arm ceiling hides it","arm B is arm A scaled by 1.35",line=3.4,subline=2.0)
text(.06,3.34,sprintf("ceilings differ: %.2f vs %.2f, but every prediction\nis identical, so the MAE difference is exactly %.0e",
     ymA,ymB,max(abs(pA-pB))),adj=0,cex=.80,col=INK)
text(2.26,.12,"open red sits exactly on filled green",adj=1,cex=.74,col=MUT)

## D - rooting depth: the trap as a monotonic runaway
par(mar=c(6.2,7.0,6.8,3.4))
D<-data.frame(d=c(60,100,120), own=c(0.593,0.451,0.411), shr=c(0.593,0.517,0.536))
yl<-c(.37,.66)
plot(NA,xlim=c(50,132),ylim=yl,axes=FALSE,xlab="",ylab="")
abline(h=pretty(yl,5),col=GRID,lwd=1)
rect(96,yl[1],104,yl[2],col="#EFEAE0",border=NA)
lines(D$d,D$own,col=CR,lwd=3.2); points(D$d,D$own,pch=19,col=CR,cex=1.5)
lines(D$d,D$shr,col=CG,lwd=3.2); points(D$d,D$shr,pch=19,col=CG,cex=1.5)
gridx(c(60,100,120),c("0.6 m","1.0 m","1.2 m"),cex=.84,line=3.0,title="rooting depth used for the bucket")
gridy(pretty(yl,5),cex=.82,line=3.4,title="leave-one-out MAE (t/ha)")
ttl("D. Rooting depth: the trap as a runaway",
    "red = each arm its own ceiling   green = ceiling as shipped",line=3.4,subline=2.0)
text(120,0.392,"deeper is always\n'better'",adj=1,cex=.80,col=CR,font=2)
text(131,0.615,"an optimum appears\nat the shipped depth",adj=1,cex=.80,col=CG,font=2)
text(100,yl[2]-.008,"shipped",adj=.5,cex=.76,col="#8A7F6C",font=2)

suptitle("Rule three: a treatment whose effect is a level shift is erased by refitting the ceiling",
 c("Yield = relative index x ceiling. If each arm is allowed its own least-squares ceiling, any pure change of level is absorbed exactly (panel C),",
   "so every test is scored twice and a win must survive the ceiling as shipped. That reversed the soil-bucket verdict (A) and dissolved an apparent gain",
   "from swapping the vegetation term (B). It also disciplines a free parameter (D): under its own ceiling rooting depth improves monotonically and 1.2 m wins",
   "significantly, which would have driven the bucket ever deeper; under the shipped ceiling an optimum appears at the 1.0 m already in use."),cex=1.16)
dev.off(); cat("fig1 ok\n")

## ================= FIGURE 2: rules one and two =================
sd_<-read.csv("Cropyield-Data/lgp_ab_seed_mae.csv",stringsAsFactors=FALSE)
A<-sd_$mae[sd_$arm=="A  fixed 120d, single Ym"]; B<-sd_$mae[sd_$arm=="B1 zone-aware LGP, single Ym"]
PX("Methodology_Testing/figs/scoring_rules.png",2060,900)
layout(matrix(1:3,1,3),widths=c(1.06,1.00,1.02))
par(mar=c(6.6,6.4,7.2,3.0),oma=c(.4,0,5.0,.4),xpd=FALSE)

## A - rule 1: one split is not a measurement
br<-seq(min(A,B)-.02,max(A,B)+.02,length.out=32); h<-hist(A,breaks=br,plot=FALSE)
yl<-c(0,max(h$counts)*1.32)
plot(NA,xlim=range(br),ylim=yl,axes=FALSE,xlab="",ylab="")
abline(h=pretty(yl,4),col=GRID,lwd=1)
rect(h$breaks[-length(h$breaks)],0,h$breaks[-1],h$counts,col=paste0(CA,"55"),border=NA)
abline(v=mean(A),col=INK,lwd=2.4)
segments(mean(A)-sd(A),yl[2]*.80,mean(A)+sd(A),yl[2]*.80,col=CR,lwd=3)
segments(c(mean(A)-sd(A),mean(A)+sd(A)),yl[2]*.77,c(mean(A)-sd(A),mean(A)+sd(A)),yl[2]*.83,col=CR,lwd=2.4)
text(mean(A)+sd(A)+.012,yl[2]*.80,sprintf("+/- 1 sd = %.3f",sd(A)),cex=.80,col=CR,font=2,adj=0)
gridx(pretty(range(br),5),cex=.80,line=3.2,title="held-out MAE from a single 70/30 split")
gridy(pretty(yl,4),cex=.80,line=3.2,title="of 500 random splits")
ttl("A. Rule 1: one split is not a measurement",
    "the same arm, 500 different random splits",line=3.6,subline=2.2)
text(min(br)+.005,yl[2]*.99,sprintf("range %.2f to %.2f t/ha,\nwider than most of the\neffects being tested",min(A),max(A)),
     adj=0,cex=.80,col=INK,font=2)

## B - rule 2: the paired bootstrap, and what "significant" means
par(mar=c(6.6,12.6,7.2,4.6))
T2<-data.frame(t=c("soil bucket, ward (shared)","LGP as cycle","S_veg swap, KE long","WHC, KE long (shared)","heat Tcap 33 vs 30"),
  d=c(-0.097,-0.085,0.0144,-0.024,0.0029),
  lo=c(-0.132,-0.169,-0.0242,-0.076,-0.0043), hi=c(-0.063,0.001,0.0536,0.023,0.0118),stringsAsFactors=FALSE)
k<-nrow(T2); xr<-c(-.20,.09)
plot(NA,xlim=xr,ylim=c(.4,k+.6),axes=FALSE,xlab="",ylab="")
abline(v=seq(-.20,.05,.05),col=GRID,lwd=1); abline(v=0,col=INK,lwd=1.6)
for(i in 1:k){y<-k-i+1; sig<-(T2$lo[i]>0)|(T2$hi[i]<0); cl<-if(sig) CR else "#ADA69A"
  segments(T2$lo[i],y,T2$hi[i],y,col=cl,lwd=2.8)
  segments(c(T2$lo[i],T2$hi[i]),y-.11,c(T2$lo[i],T2$hi[i]),y+.11,col=cl,lwd=2.2)
  points(T2$d[i],y,pch=19,col=cl,cex=1.15)
  text(.095,y,if(sig)"counts" else "does not count",adj=0,cex=.74,col=cl,font=2,xpd=NA)}
gridy(k:1,T2$t,cex=.80)
gridx(seq(-.20,.05,.05),cex=.78,line=3.2,title="paired-bootstrap 95% interval on the LOO-MAE difference")
ttl("B. Rule 2: the interval must clear zero",
    "2,000 resamples, both arms on the same resample",line=3.6,subline=2.2)

## C - rule 3: rank is ceiling-invariant
par(mar=c(6.6,10.6,7.2,3.4))
R<-data.frame(t=c("WHC, KE long","WHC, KE short","WHC, ward 2021","S_veg, KE long","S_veg, KE short"),
  A=c(0.724,0.101,-0.161,0.737,0.594), B=c(0.736,0.091,-0.177,0.754,0.617),stringsAsFactors=FALSE)
m<-nrow(R)
plot(NA,xlim=c(-.32,.92),ylim=c(.4,m+.6),axes=FALSE,xlab="",ylab="")
abline(v=seq(-.3,.9,.3),col=GRID,lwd=1); abline(v=0,col=MUT,lwd=1.2)
for(i in 1:m){y<-m-i+1
  segments(R$A[i],y,R$B[i],y,col=RULE,lwd=2.4)
  points(R$B[i],y,pch=19,col=CB,cex=1.45)
  points(R$A[i],y,pch=21,bg="white",col=CA,lwd=2.4,cex=1.45)
  text(.94,y,sprintf("%+.3f",R$B[i]-R$A[i]),adj=0,cex=.74,col=MUT,xpd=NA)}
gridy(m:1,R$t,cex=.80)
gridx(seq(-.3,.9,.3),cex=.80,line=3.2,title="Spearman rank correlation")
ttl("C. Rule 3: rank is ceiling-proof",
    "open = arm A, filled = arm B",line=3.6,subline=2.2)
text(.94,m+.42,"delta",adj=0,cex=.72,col=MUT,font=2,xpd=NA)
suptitle("The scoring protocol, and what each rule is defending against",
 c("Rule 1 guards against reading a single random split as a measurement: the same arm re-split 500 times spans 0.34 to 0.88 t/ha.",
   "Rule 2 requires the paired-bootstrap interval to clear zero, so a difference smaller than the resampling noise is not reported as a result.",
   "Rule 3 reports rank alongside error because Spearman is invariant to the yield ceiling - it is the one statistic a refitted ceiling cannot touch."))
dev.off(); cat("fig2 ok\n")
