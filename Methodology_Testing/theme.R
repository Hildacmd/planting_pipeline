# Shared visual language for the OND window assessment.
INK<-"#1E1B18"; TX2<-"#4A453E"; MUT<-"#7E766B"; GRID<-"#E3DED4"; RULE<-"#CFC8BC"
PAL<-c(one="#3E7A47", held="#C98A1E", two="#B8432A", e="#1F6FB2", l="#B8432A", n="#5B7C99")
WIN_E<-"#DCE9F5"; WIN_L<-"#F6E2D9"; ACC<-"#7A5EA8"
PX<-function(f,w,h) png(f,w,h,res=170)
# axis helpers: recessive grid, no box, tabular labels
gridx<-function(at,lab=NULL,cex=.80,las=1,line=2.9,title=NULL){
  axis(1,at=at,labels=if(is.null(lab)) at else lab,col=GRID,col.axis=MUT,cex.axis=cex,las=las,
       tck=-.018,lwd=1,lwd.ticks=1)
  if(!is.null(title)) mtext(title,1,line=line,cex=cex*1.02,col=MUT)}
gridy<-function(at,lab=NULL,cex=.80,line=3.4,title=NULL){
  axis(2,at=at,labels=if(is.null(lab)) at else lab,las=1,col=GRID,col.axis=MUT,cex.axis=cex,tck=-.018)
  if(!is.null(title)) mtext(title,2,line=line,cex=cex*1.02,col=MUT)}
ttl<-function(main,sub=NULL,line=2.2,subline=0.9,cex=1.02){
  mtext(main,3,line=line,adj=0,cex=cex,font=2,col=INK)
  if(!is.null(sub)) mtext(sub,3,line=subline,adj=0,cex=cex*.72,col=MUT)}
suptitle<-function(main,subs=character(0),cex=1.18){
  par(fig=c(0,1,0,1),oma=c(0,0,0,0),mar=c(0,0,0,0),new=TRUE,xpd=NA)
  plot(0:1,0:1,type="n",axes=FALSE,xlab="",ylab="")
  mtext(main,3,line=-1.9,adj=.012,cex=cex,font=2,col=INK)
  for(i in seq_along(subs)) mtext(subs[i],3,line=-3.1-1.15*(i-1),adj=.012,cex=cex*.66,col=MUT)}
MON<-c("Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec")
dl<-function(x){ if(length(x)>1) return(sapply(x,dl))
  if(is.na(x)) return("-"); x<-round(x); m<-((x-1)%%36)
  sprintf("%s-d%d%s",MON[m%/%3+1],m%%3+1,if(x>36)"+" else "")}
dshort<-function(x) sub("-d","",dl(x))

# Linear interpolation across INTERNAL gaps only (leading/trailing NAs are left alone).
# Used so a cloud-masked dekad does not break the line; observed points are drawn separately
# so the reader can still see which values were actually measured.
fillgap<-function(v){ ok<-which(!is.na(v)); if(length(ok)<2) return(v)
  out<-v; idx<-ok[1]:ok[length(ok)]
  out[idx]<-approx(ok,v[ok],xout=idx)$y; out }
